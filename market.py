import datetime
import logging.config
from environs import Env
from seller import download_stock

import requests

from seller import divide, price_conversion

logger = logging.getLogger(__file__)

def get_product_list(page, campaign_id, access_token):
    """Получает список товаров из Яндекс Маркета.
    
    Args:
        page (str): Токен страницы для пагинации.
        campaign_id (str): Идентификатор кампании.
        access_token (str): Токен доступа к API.
    
    Returns:
        dict: Результат запроса с товарами.
    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {"page_token": page, "limit": 200}
    url = endpoint_url + f"campaigns/{campaign_id}/offer-mapping-entries"
    response = requests.get(url, headers=headers, params=payload)
    response.raise_for_status()
    return response.json().get("result")

def update_stocks(stocks, campaign_id, access_token):
    """Обновляет остатки товаров на Яндекс Маркете.
    
    Args:
        stocks (list): Список остатков товаров.
        campaign_id (str): Идентификатор кампании.
        access_token (str): Токен доступа к API.
    
    Returns:
        dict: Результат обновления остатков.
    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {"skus": stocks}
    url = endpoint_url + f"campaigns/{campaign_id}/offers/stocks"
    response = requests.put(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()

def update_price(prices, campaign_id, access_token):
    """Обновляет цены товаров на Яндекс Маркете.
    
    Args:
        prices (list): Список цен товаров.
        campaign_id (str): Идентификатор кампании.
        access_token (str): Токен доступа к API.
    
    Returns:
        dict: Результат обновления цен.
    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {"offers": prices}
    url = endpoint_url + f"campaigns/{campaign_id}/offer-prices/updates"
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()

def get_offer_ids(campaign_id, market_token):
    """Получает артикулы товаров из Яндекс Маркета.
    
    Args:
        campaign_id (str): Идентификатор кампании.
        market_token (str): Токен доступа к API.
    
    Returns:
        list: Список артикулов товаров.
    """
    page = ""
    product_list = []
    while True:
        some_prod = get_product_list(page, campaign_id, market_token)
        product_list.extend(some_prod.get("offerMappingEntries"))
        page = some_prod.get("paging").get("nextPageToken")
        if not page:
            break
    return [product.get("offer").get("shopSku") for product in product_list]

def create_stocks(watch_remnants, offer_ids, warehouse_id):
    """Создает список остатков для обновления.
    
    Args:
        watch_remnants (list): Остатки товаров.
        offer_ids (list): Список артикулов товаров.
        warehouse_id (str): Идентификатор склада.
    
    Returns:
        list: Готовые данные для обновления остатков.
    """
    stocks = []
    date = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            count = watch.get("Количество")
            stock = 100 if count == ">10" else (0 if count == "1" else int(count))
            stocks.append({
                "sku": str(watch.get("Код")),
                "warehouseId": warehouse_id,
                "items": [{"count": stock, "type": "FIT", "updatedAt": date}],
            })
            offer_ids.remove(str(watch.get("Код")))
    for offer_id in offer_ids:
        stocks.append({
            "sku": offer_id,
            "warehouseId": warehouse_id,
            "items": [{"count": 0, "type": "FIT", "updatedAt": date}],
        })
    return stocks

def create_prices(watch_remnants, offer_ids):
    """
    Создает список цен для товаров, которые есть в Яндекс.Маркете.

    Args:
        watch_remnants (list): Список остатков товаров.
        offer_ids (list): Список артикулов товаров в Яндекс.Маркете.

    Returns:
        list: Список цен для обновления на Яндекс.Маркете.
    """
    prices = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            price = {
                "id": str(watch.get("Код")),
                "price": {
                    "value": int(price_conversion(watch.get("Цена"))),
                    "currencyId": "RUR",
                },
            }
            prices.append(price)
    return prices


async def upload_prices(watch_remnants, campaign_id, market_token):
    """
    Загружает обновленные цены товаров в Яндекс.Маркет.

    Args:
        watch_remnants (list): Список остатков товаров.
        campaign_id (str): ID кампании в Яндекс.Маркете.
        market_token (str): Токен доступа к API Яндекс.Маркета.

    Returns:
        list: Список загруженных цен.
    """
    offer_ids = get_offer_ids(campaign_id, market_token)
    prices = create_prices(watch_remnants, offer_ids)
    for some_prices in list(divide(prices, 500)):
        update_price(some_prices, campaign_id, market_token)
    return prices


async def upload_stocks(watch_remnants, campaign_id, market_token, warehouse_id):
    """
    Загружает обновленные остатки товаров в Яндекс.Маркет.

    Args:
        watch_remnants (list): Список остатков товаров.
        campaign_id (str): ID кампании в Яндекс.Маркете.
        market_token (str): Токен доступа к API Яндекс.Маркета.
        warehouse_id (str): ID склада в Яндекс.Маркете.

    Returns:
        tuple: Список товаров с ненулевым остатком и общий список остатков.
    """
    offer_ids = get_offer_ids(campaign_id, market_token)
    stocks = create_stocks(watch_remnants, offer_ids, warehouse_id)
    for some_stock in list(divide(stocks, 2000)):
        update_stocks(some_stock, campaign_id, market_token)
    not_empty = list(
        filter(lambda stock: (stock.get("items")[0].get("count") != 0), stocks)
    )
    return not_empty, stocks

def main():
    """Основная функция для обновления остатков и цен на Яндекс Маркете."""
    env = Env()
    market_token = env.str("MARKET_TOKEN")
    campaign_fbs_id = env.str("FBS_ID")
    campaign_dbs_id = env.str("DBS_ID")
    warehouse_fbs_id = env.str("WAREHOUSE_FBS_ID")
    warehouse_dbs_id = env.str("WAREHOUSE_DBS_ID")

    watch_remnants = download_stock()
    try:
        for campaign_id, warehouse_id in [(campaign_fbs_id, warehouse_fbs_id), (campaign_dbs_id, warehouse_dbs_id)]:
            offer_ids = get_offer_ids(campaign_id, market_token)
            stocks = create_stocks(watch_remnants, offer_ids, warehouse_id)
            for some_stock in list(divide(stocks, 2000)):
                update_stocks(some_stock, campaign_id, market_token)
            upload_prices(watch_remnants, campaign_id, market_token)
    except requests.exceptions.ReadTimeout:
        print("Превышено время ожидания...")
    except requests.exceptions.ConnectionError as error:
        print(error, "Ошибка соединения")
    except Exception as error:
        print(error, "ERROR_2")

if __name__ == "__main__":
    main()
