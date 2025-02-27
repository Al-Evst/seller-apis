import io
import logging.config
import os
import re
import zipfile
from environs import Env

import pandas as pd
import requests

logger = logging.getLogger(__file__)


def get_product_list(last_id, client_id, seller_token):
    """Получает список товаров магазина Ozon.

    Args:
        last_id (str): Последний идентификатор товара.
        client_id (str): Идентификатор клиента Ozon.
        seller_token (str): Токен продавца Ozon.

    Returns:
        dict: Результат запроса со списком товаров.

    Example:
        >>> get_product_list("", "12345", "token")
        {'items': [...], 'total': 100, 'last_id': 'abc123'}
    """
    url = "https://api-seller.ozon.ru/v2/product/list"
    headers = {"Client-Id": client_id, "Api-Key": seller_token}
    payload = {"filter": {"visibility": "ALL"}, "last_id": last_id, "limit": 1000}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json().get("result")


def get_offer_ids(client_id, seller_token):
    """Получает список артикулов товаров магазина Ozon.

    Args:
        client_id (str): Идентификатор клиента Ozon.
        seller_token (str): Токен продавца Ozon.

    Returns:
        list: Список offer_id товаров.

    Example:
        >>> get_offer_ids("12345", "token")
        ['offer1', 'offer2', 'offer3']
    """
    last_id = ""
    product_list = []
    while True:
        some_prod = get_product_list(last_id, client_id, seller_token)
        product_list.extend(some_prod.get("items"))
        total = some_prod.get("total")
        last_id = some_prod.get("last_id")
        if total == len(product_list):
            break
    return [product.get("offer_id") for product in product_list]


def update_price(prices, client_id, seller_token):
    """Обновляет цены товаров.

    Args:
        prices (list): Список словарей с информацией о цене.
        client_id (str): Идентификатор клиента Ozon.
        seller_token (str): Токен продавца Ozon.

    Returns:
        dict: Ответ от API Ozon.
    """
    url = "https://api-seller.ozon.ru/v1/product/import/prices"
    headers = {"Client-Id": client_id, "Api-Key": seller_token}
    response = requests.post(url, json={"prices": prices}, headers=headers)
    response.raise_for_status()
    return response.json()


def update_stocks(stocks, client_id, seller_token):
    """Обновляет остатки товаров.

    Args:
        stocks (list): Список словарей с остатками.
        client_id (str): Идентификатор клиента Ozon.
        seller_token (str): Токен продавца Ozon.

    Returns:
        dict: Ответ от API Ozon.
    """
    url = "https://api-seller.ozon.ru/v1/product/import/stocks"
    headers = {"Client-Id": client_id, "Api-Key": seller_token}
    response = requests.post(url, json={"stocks": stocks}, headers=headers)
    response.raise_for_status()
    return response.json()


def price_conversion(price: str) -> str:
    """Преобразует строку цены в числовую строку без лишних символов.

    Args:
        price (str): Строка цены (например, "5'990.00 руб.").

    Returns:
        str: Числовая строка (например, "5990").
    """
    return re.sub("[^0-9]", "", price.split(".")[0])


def divide(lst, n):
    """Разделяет список на части по n элементов.

    Args:
        lst (list): Исходный список.
        n (int): Размер подсписков.

    Yields:
        list: Подсписки по n элементов.
    """
    for i in range(0, len(lst), n):
        yield lst[i: i + n]


def main():
    """Главная функция для обновления цен и остатков на Ozon."""
    env = Env()
    seller_token = env.str("SELLER_TOKEN")
    client_id = env.str("CLIENT_ID")
    try:
        offer_ids = get_offer_ids(client_id, seller_token)
        watch_remnants = download_stock()
        stocks = create_stocks(watch_remnants, offer_ids)
        for some_stock in divide(stocks, 100):
            update_stocks(some_stock, client_id, seller_token)
        prices = create_prices(watch_remnants, offer_ids)
        for some_price in divide(prices, 900):
            update_price(some_price, client_id, seller_token)
    except requests.exceptions.ReadTimeout:
        print("Превышено время ожидания...")
    except requests.exceptions.ConnectionError as error:
        print(error, "Ошибка соединения")
    except Exception as error:
        print(error, "ERROR_2")


if __name__ == "__main__":
    main()
