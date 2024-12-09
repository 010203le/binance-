from flask import Flask, jsonify, request
from dotenv import load_dotenv
import os
import time
import hmac
import hashlib
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# 幣安 API 金鑰
load_dotenv()
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
BASE_URL = "https://fapi.binance.com"  # USDⓈ 合約
COIN_BASE_URL = "https://dapi.binance.com"  # 幣本位合約

# 創建簽名
def create_signature(query_string, secret):
    return hmac.new(secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()

# 發送請求
def send_signed_request(http_method, base_url, endpoint, params=None):
    if not params:
        params = {}
    params['timestamp'] = int(time.time() * 1000)
    query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
    signature = create_signature(query_string, API_SECRET)
    headers = {'X-MBX-APIKEY': API_KEY}
    url = f"{base_url}{endpoint}?{query_string}&signature={signature}"
    response = requests.request(http_method, url, headers=headers)
    return response.json()

# 獲取合約餘額（美元合約和幣本位合約）
@app.route('/account-balance', methods=['GET'])
def get_account_balance():
    # 獲取合約餘額
    usd_balance = send_signed_request("GET", BASE_URL, "/fapi/v3/balance")
    coin_balance = send_signed_request("GET", COIN_BASE_URL, "/dapi/v1/balance")
    
    # 獲取市場價格
    prices = requests.get("https://api.binance.com/api/v3/ticker/price").json()
    price_dict = {item['symbol']: float(item['price']) for item in prices}
    price_dict["BFUSDUSDT"] = 1  # 這是固定的USD對美元兌換率，通常為1

    # 計算美元計價的總餘額
    def calculate_usd_balance(balance_list, price_dict):
        total_usd_balance = 0
        seen_assets = set()  # 記錄已處理的資產，避免重複計算

        # 計算資產餘額
        for item in balance_list:
            asset = item['asset']
            balance = float(item['crossWalletBalance'])
            if balance > 0:
                seen_assets.add(asset)  # 標記該資產已處理
                if asset == "USDT":
                    total_usd_balance += balance
                else:
                    symbol = f"{asset}USDT"
                    price = price_dict.get(symbol, 0)
                    total_usd_balance += balance * price

        return total_usd_balance
         
    # 計算美元計價的合約和幣本位合約餘額
    total_usd_balance = calculate_usd_balance(usd_balance, price_dict)
    total_coin_balance = calculate_usd_balance(coin_balance, price_dict)

    # 返回結果
    return jsonify({
        "usd_balance": total_usd_balance,  # 直接返回美元計價餘額
        "coin_balance": total_coin_balance,  # 幣本位合約餘額
        "total_balance": total_usd_balance + total_coin_balance  # 總餘額
    })



# 獲取持倉（美元合約和幣本位合約）
@app.route('/positions', methods=['GET'])
def get_positions():
    usd_positions = send_signed_request("GET", BASE_URL, "/fapi/v2/positionRisk")
    coin_positions = send_signed_request("GET", COIN_BASE_URL, "/dapi/v1/positionRisk")
    return jsonify({"usd": usd_positions, "coin": coin_positions})

# 資金流水（包含 Funding Fee）
@app.route('/funding-history', methods=['GET'])
def get_funding_history():
    try:

        # 构造请求参数
        params = {
            "incomeType": 'FUNDING_FEE',

        }
        # 移除值为 None 的参数
        params = {k: v for k, v in params.items() if v is not None}

        # 发起 API 请求
        usd_funding_data = send_signed_request("GET", BASE_URL, "/fapi/v1/income", params)
        coin_funding_data = send_signed_request("GET", COIN_BASE_URL, "/dapi/v1/income", params)

        # 返回结果
        return jsonify({"usd": usd_funding_data, "coin": coin_funding_data})
    except Exception as e:
        print(e)

if __name__ == '__main__':
    app.run()
