import yaml
import json
import pandas as pd
from api_helper import ShoonyaApiPy
import math

def main():
    # Initialize the API
    api = ShoonyaApiPy()

    # Load credentials from the YAML file
    with open('cred.yml') as f:
        cred = yaml.safe_load(f)

    # Login to the API
    login_response = api.login(userid=cred['user'], password=cred['pwd'], twoFA=cred['factor2'],
                               vendor_code=cred['vc'], api_secret=cred['apikey'], imei=cred['imei'])
    if login_response['stat'] != 'Ok':
        print("Failed to log in:", login_response['emsg'])
        return
    print("Logged in successfully!")

    # Main trading loop
    try:
        while True:
            current_price, options = fetch_banknifty_data(api)
            if current_price is None or options is None:
                continue

            cheaper_option = decide_option_to_buy(current_price, options)
            if cheaper_option:
                place_trade(api, cheaper_option)
    except KeyboardInterrupt:
        print("Exiting the trading loop.")

    # Logout from the API
    logout_response = api.logout()
    if logout_response['stat'] == 'Ok':
        print("Logged out successfully.")
    else:
        print("Failed to log out:", logout_response['emsg'])

def fetch_banknifty_data(api):
    try:
        # Fetching current price for Bank Nifty
        banknifty_quote = api.get_quotes(exchange='NSE', token='26009')  # Bank Nifty token
        
        if not banknifty_quote or 'lp' not in banknifty_quote:
            print("Market may be closed or data unavailable.")
            return None, None
        
        current_price = float(banknifty_quote['lp'])

        # Fetching options chain for Bank Nifty
        option_chain_response = api.get_option_chain(
            exchange='NFO',
            tradingsymbol='BANKNIFTY',
            strikeprice=current_price,
            count=5
        )

        if option_chain_response is None or 'values' not in option_chain_response:
            print("Failed to fetch option chain: Market may be closed or response is empty.")
            return None, None

        option_chain_data = option_chain_response['values']

        calls = pd.DataFrame([opt for opt in option_chain_data if opt.get('optt') == 'CE'])
        puts = pd.DataFrame([opt for opt in option_chain_data if opt.get('optt') == 'PE'])

        options = {
            'calls': calls,
            'puts': puts
        }

        return current_price, options
    except Exception as e:
        print(f"Failed to fetch or parse Bank Nifty data: {e}")
        return None, None

    
def decide_option_to_buy(current_price, options):
    strike_interval = 100  # Bank Nifty strike interval
    nearest_strike_call = math.ceil(current_price / 100) * 100
    nearest_strike_put = math.floor(current_price / 100) * 100

    call_option = options['calls'].loc[options['calls']['strikePrice'] == nearest_strike_call].iloc[0]
    put_option = options['puts'].loc[options['puts']['strikePrice'] == nearest_strike_put].iloc[0]

    if abs(current_price - nearest_strike_put) < abs(nearest_strike_call - current_price):
        return put_option if put_option['lastPrice'] <= call_option['lastPrice'] else call_option
    else:
        return call_option if call_option['lastPrice'] < put_option['lastPrice'] else put_option

def place_trade(api, option):
    order_response = api.place_order(
        buy_or_sell='B',
        product_type='C',
        exchange='NSE',
        tradingsymbol=option['tradingsymbol'],
        quantity=1,
        discloseqty=0, 
        price_type='LMT',
        price=option['lastPrice'],
        retention='DAY',
        remarks='Automated trade'
    )
    if order_response.get('stat') == 'Ok':
        print(f"Order placed successfully: {order_response}")
    else:
        print(f"Failed to place order: {order_response.get('emsg')}")

if __name__ == '__main__':
    main()
