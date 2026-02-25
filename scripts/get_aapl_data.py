import yfinance as yf
import json
from datetime import datetime

def get_stock_data(ticker_symbol):
    """
    Fetches comprehensive stock data from yfinance.
    """
    ticker = yf.Ticker(ticker_symbol)
    
    data = {}
    
    # Basic Info
    data['info'] = ticker.info

    # Financial Statements
    data['income_stmt_quarterly'] = ticker.quarterly_income_stmt.to_json(orient='split')
    data['balance_sheet_quarterly'] = ticker.quarterly_balance_sheet.to_json(orient='split')
    data['cashflow_quarterly'] = ticker.quarterly_cashflow.to_json(orient='split')

    # Earnings and Estimates
    data['earnings_dates'] = str(ticker.get_earnings_dates())
    data['earnings_history'] = ticker.get_earnings_history().to_json(orient='split')
    data['earnings_estimate'] = ticker.get_earnings_estimate().to_json(orient='split')
    data['eps_trend'] = ticker.get_eps_trend().to_json(orient='split')
    
    # Recommendations
    data['recommendations'] = ticker.get_recommendations_summary().to_json(orient='split')
    data['upgrades_downgrades'] = ticker.get_upgrades_downgrades().head(20).to_json(orient='split')

    # News
    data['news'] = ticker.get_news()

    return data

if __name__ == '__main__':
    aapl_data = get_stock_data('AAPL')
    # Use default=str to handle any non-serializable data types
    print(json.dumps(aapl_data, indent=4, default=str))
