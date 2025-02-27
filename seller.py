import io
import logging.config
import os
import re
import zipfile
from environs import Env

import pandas as pd
import requests

logger = logging.getLogger(__file__)

def get_product_list(last_id: str, client_id: str, seller_token: str) -> dict:
    """Получает список товаров магазина Ozon.

    Args:
        last_id (str): Последний ID, с которого начинать загрузку.
        client_id (str): Идентификатор клиента Ozon.
        seller_token (str): Токен продавца.

    Returns:
        dict: Список товаров.
    
    Raises:
        requests.exceptions.RequestException: В случае ошибки запроса.

    Example:
        >>> get_product_list("", "12345", "token")
    """
    url = "https://api-seller.ozon.ru/v2/product/list"
    headers = {"Client-Id": client_id, "Api-Key": seller_token}
    payload = {"filter": {"visibility": "ALL"}, "last_id": last_id, "limit": 1000}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json().get("result")

def get_offer_ids(client_id: str, seller_token: str) -> list:
    """Получает список артикулов товаров магазина Ozon.

    Args:
        client_id (str): Идентификатор клиента Ozon.
        seller_token (str): Токен продавца.

    Returns:
        list: Список артикулов (offer_id).

    Example:
        >>> get_offer_ids("12345", "token")
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

def update_price(prices: list, client_id: str, seller_token: str) -> dict:
    """Обновляет цены товаров на Ozon.

    Args:
        prices (list): Список цен.
        client_id (str): Идентификатор клиента Ozon.
        seller_token (str): Токен продавца.

    Returns:
        dict: Ответ API Ozon.
    """
    url = "https://api-seller.ozon.ru/v1/product/import/prices"
    headers = {"Client-Id": client_id, "Api-Key": seller_token}
    response = requests.post(url, json={"prices": prices}, headers=headers)
    response.raise_for_status()
    return response.json()

def download_stock() -> list:
    """Скачивает и обрабатывает файл остатков с сайта Casio.

    Returns:
        list: Список остатков товаров.
    """
    casio_url = "https://timeworld.ru/upload/files/ostatki.zip"
    response = requests.get(casio_url)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        archive.extractall(".")
    excel_file = "ostatki.xls"
    watch_remnants = pd.read_excel(excel_file, header=17).to_dict(orient="records")
    os.remove(excel_file)
    return watch_remnants

def price_conversion(price: str) -> str:
    """Преобразует цену в числовой формат.

    Args:
        price (str): Цена в строковом формате.

    Returns:
        str: Числовая цена без лишних символов.

    Example:
        >>> price_conversion("5'990.00 руб.")
        '5990'
    """
    return re.sub("[^0-9]", "", price.split(".")[0])

def main():
    """Основная функция запуска обновления остатков и цен на Ozon."""
    env = Env()
    seller_token = env.str("SELLER_TOKEN")
    client_id = env.str("CLIENT_ID")
    try:
        offer_ids = get_offer_ids(client_id, seller_token)
        watch_remnants = download_stock()
        prices = [{
            "auto_action_enabled": "UNKNOWN", "currency_code": "RUB", "offer_id": str(watch["Код"]),
            "old_price": "0", "price": price_conversion(watch["Цена"])
        } for watch in watch_remnants if str(watch["Код"]) in offer_ids]
        for some_price in divide(prices, 900):
            update_price(some_price, client_id, seller_token)
    except requests.exceptions.RequestException as error:
        print(f"Ошибка запроса: {error}")
    except Exception as error:
        print(f"Произошла ошибка: {error}")

if __name__ == "__main__":
    main()
