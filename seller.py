import io
import logging.config
import os
import re
import zipfile
from environs import Env

import pandas as pd
import requests

def get_product_list(last_id: str, client_id: str, seller_token: str) -> dict:
    """
    Получить список товаров магазина Ozon.

    Args:
        last_id (str): Последний ID товара из предыдущего запроса.
        client_id (str): Идентификатор клиента Ozon.
        seller_token (str): API-ключ продавца Ozon.

    Returns:
        dict: Словарь с результатами запроса, содержащий список товаров.

    Raises:
        requests.HTTPError: В случае ошибки HTTP-запроса.
    """
    url = "https://api-seller.ozon.ru/v2/product/list"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {
        "filter": {
            "visibility": "ALL",
        },
        "last_id": last_id,
        "limit": 1000,
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    response_object = response.json()
    return response_object.get("result", {})

def get_offer_ids(client_id: str, seller_token: str) -> list:
    """
    Получить артикулы (offer_id) товаров магазина Ozon.

    Args:
        client_id (str): Идентификатор клиента Ozon.
        seller_token (str): API-ключ продавца Ozon.

    Returns:
        list: Список артикулов товаров (offer_id).
    """
    last_id = ""
    product_list = []
    while True:
        some_prod = get_product_list(last_id, client_id, seller_token)
        product_list.extend(some_prod.get("items", []))
        total = some_prod.get("total", 0)
        last_id = some_prod.get("last_id", "")
        if total == len(product_list):
            break
    
    offer_ids = [product.get("offer_id") for product in product_list]
    return offer_ids

def update_price(prices: list, client_id: str, seller_token: str) -> dict:
    """
    Обновляет цены товаров на платформе Ozon.

    Args:
        prices (list): Список цен на товары.
        client_id (str): Идентификатор клиента.
        seller_token (str): Токен продавца.

    Returns:
        dict: Ответ API в формате JSON.
    
    Raises:
        requests.exceptions.HTTPError: Если запрос завершился с ошибкой.
    """
    url = "https://api-seller.ozon.ru/v1/product/import/prices"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {"prices": prices}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()

def update_stocks(stocks: list, client_id: str, seller_token: str) -> dict:
    """
    Обновляет остатки товаров на платформе Ozon.

    Args:
        stocks (list): Список остатков товаров.
        client_id (str): Идентификатор клиента.
        seller_token (str): Токен продавца.

    Returns:
        dict: Ответ API в формате JSON.
    
    Raises:
        requests.exceptions.HTTPError: Если запрос завершился с ошибкой.
    """
    url = "https://api-seller.ozon.ru/v1/product/import/stocks"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {"stocks": stocks}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()

def download_stock():
    """Скачать файл ostatki с сайта casio.

    Returns:
        list: A list of dictionaries containing watch stock data.
    """
    casio_url = "https://timeworld.ru/upload/files/ostatki.zip"
    session = requests.Session()
    response = session.get(casio_url)
    response.raise_for_status()
    
    with response, zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        archive.extractall(".")
    
    excel_file = "ostatki.xls"
    watch_remnants = pd.read_excel(
        io=excel_file,
        na_values=None,
        keep_default_na=False,
        header=17,
    ).to_dict(orient="records")
    
    os.remove("./ostatki.xls")
    return watch_remnants

def create_stocks(watch_remnants, offer_ids):
    """Создает список запасов для часов на основе имеющихся данных о запасах.

    Args:
        watch_remnants (list): List of dictionaries containing watch stock data.
        offer_ids (set): Set of offer IDs to filter the stock data.

    Returns:
        list: A list of dictionaries containing offer_id and stock quantity.
    """
    stocks = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            count = str(watch.get("Количество"))
            if count == ">10":
                stock = 100
            elif count == "1":
                stock = 0
            else:
                stock = int(watch.get("Количество"))
            stocks.append({"offer_id": str(watch.get("Код")), "stock": stock})
            offer_ids.remove(str(watch.get("Код")))
    
    for offer_id in offer_ids:
        stocks.append({"offer_id": offer_id, "stock": 0})
    
    return stocks

def create_prices(watch_remnants, offer_ids):
    """Создает прайс-лист для часов на основе имеющихся данных о ценах.

    Args:
        watch_remnants (list): List of dictionaries containing watch price data.
        offer_ids (set): Set of offer IDs to filter the price data.

    Returns:
        list: A list of dictionaries containing offer_id, price, and currency code.
    """
    prices = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            price = {
                "auto_action_enabled": "UNKNOWN",
                "currency_code": "RUB",
                "offer_id": str(watch.get("Код")),
                "old_price": "0",
                "price": price_conversion(watch.get("Цена")),
            }
            prices.append(price)
    
    return prices

def price_conversion(price: str) -> str:
    """Преобразовать цену. Пример: 5'990.00 руб. -> 5990.

    Example:
        '5'990.00 руб.' -> '5990'

    Args:
        price (str): Price string with currency symbols and formatting.

    Returns:
        str: Cleaned price string with only numeric values.
    """
    return re.sub("[^0-9]", "", price.split(".")[0])

def divide(lst: list, n: int):
    """Разделить список lst на части по n элементов.

    Args:
        lst (list): The list to be divided.
        n (int): The size of each chunk.

    Returns:
        list: A sublist of n elements from the original list.
    """
    for i in range(0, len(lst), n):
        yield lst[i : i + n]

async def upload_prices(watch_remnants, client_id, seller_token):
    """Пакетная загрузка данных о ценах на сервер.

    Args:
        watch_remnants (list): List of dictionaries containing watch data.
        client_id (str): The client ID for authentication.
        seller_token (str): The seller token for API authorization.

    Returns:
        list: List of downloaded price data.
    """
    offer_ids = get_offer_ids(client_id, seller_token)
    prices = create_prices(watch_remnants, offer_ids)
    for some_price in list(divide(prices, 1000)):
        update_price(some_price, client_id, seller_token)
    return prices

async def upload_stocks(watch_remnants, client_id, seller_token):
    """Пакетная загрузка данных о запасах на сервер.

    Args:
        watch_remnants (list): List of dictionaries containing stock data.
        client_id (str): The client ID for authentication.
        seller_token (str): The seller token for API authorization.

    Returns:
        tuple: кортеж, содержащий список непустых акций и всех акций.
    """
    offer_ids = get_offer_ids(client_id, seller_token)
    stocks = create_stocks(watch_remnants, offer_ids)
    for some_stock in list(divide(stocks, 100)):
        update_stocks(some_stock, client_id, seller_token)
    not_empty = list(filter(lambda stock: (stock.get("stock") != 0), stocks))
    return not_empty, stocks

def main():
    """Основная функция - обработка информации о запасах и ценах."""
    env = Env()
    seller_token = env.str("SELLER_TOKEN")
    client_id = env.str("CLIENT_ID")
    try:
        offer_ids = get_offer_ids(client_id, seller_token)
        watch_remnants = download_stock()
        
        # Update stocks
        stocks = create_stocks(watch_remnants, offer_ids)
        for some_stock in list(divide(stocks, 100)):
            update_stocks(some_stock, client_id, seller_token)
        
        # Update prices
        prices = create_prices(watch_remnants, offer_ids)
        for some_price in list(divide(prices, 900)):
            update_price(some_price, client_id, seller_token)
    except requests.exceptions.ReadTimeout:
        print("Превышено время ожидания...")
    except requests.exceptions.ConnectionError as error:
        print(error, "Ошибка соединения")
    except Exception as error:
        print(error, "ERROR_2")

if __name__ == "__main__":
    main()
