import os
import statistics
from datetime import datetime, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from lemon import api
from pytz import utc

load_dotenv()
# create your api client with separate trading and market data api tokens
client = api.create(
    trading_api_token=os.environ.get('PAPER_TRADING_API_KEY'),
    market_data_api_token=os.environ.get('DATA_API_KEY'),
    env='paper'
)


def mean_reversion_decision(isin: str, x1: str = "d1"):
    """
    :param isin: pass the isin of your instrument
    :param x1: pass what type of data you want to retrieve (m1, h1 or d1)
    :return: returns whether you should buy (True) or sell (False), depending on MR criteria
    """
    from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    market_data = client.market_data.ohlc.get(
        isin=isin,
        from_=from_date,
        period=x1
    )

    d1_prices = market_data.results
    prices_close = [x.c for x in d1_prices]  # you can obviously change that to low, close or open
    mean_price = statistics.mean(prices_close)
    print(f'Mean Price: {mean_price}')
    latest_close_price = client.market_data.ohlc.get(
        isin=isin,
        from_='latest',
        period="m1"
    ).results[0].c
    print(f'Latest Close Price: {latest_close_price}')
    if latest_close_price < mean_price:
        return True
    return False


def mean_reversion(isin: str = "DE0007664039", x1: str = "d1"):
    """
    :param isin: pass the isin of the stock you are interested in,
                the default is Volkswagen here, but you can obviously use any ISIN you like :)
    :param x1:  pass the market data format you are interested in (m1, h1, or d1)
    """
    load_dotenv()
    quantity = 1
    price = client.market_data.ohlc.get(
        isin=isin,
        from_="latest",
        period=x1
    ).results[0].c
    if price * quantity < 50:
        print(f"This order totals, €{price * quantity}, which is below the minimum of €50.")
    # check for MR decision
    if mean_reversion_decision(
            isin=isin,
            x1=x1
    ):
        # create a buy order if True is returned by MR decision function
        try:
            print('buy')
            placed_order = client.trading.orders.create(
                isin=isin,
                expires_at=7,
                side="buy",
                quantity=quantity,
                venue=os.getenv("MIC"),
            )
            order_id = placed_order.results.id
            # subsequently activate the order
            activated_order = client.trading.orders.activate(order_id)
            print(activated_order)
        except Exception as e:
            print(f'1{e}')
    else:
        try:
            # create a sell order if mean reversion decision returns False
            print('sell')
            placed_order = client.trading.orders.create(
                isin=isin,
                expires_at=7,
                side="sell",
                quantity=quantity,
                venue=os.getenv("MIC"),
            )
            # if position in portfolio, activate order
            if placed_order is not None:
                order_id = placed_order.results.id
                activated_order = client.trading.orders.activate(order_id)
                print(activated_order)
            else:
                print("You do not have sufficient holdings to place this order.")
        except Exception as e:
            print(f'2{e}')


def schedule_trades_for_year():
    opening_days = client.market_data.venues.get().results[0].opening_days

    for day in opening_days:
        # using venues endpoint we only schedule trades for days the exchange is open
        for x in range(13):
            # using a scheduler, we run the mean reversion logic once per hour starting from 8:30
            # (based on Munich Stock Exchange hours with times in UTC)
            scheduler.add_job(mean_reversion,
                              trigger=CronTrigger(year=day.year,
                                                  month=day.month,
                                                  day=day.day,
                                                  hour=8 + x,
                                                  minute=30,
                                                  timezone=utc),
                              name="Perform Mean Reversion Hourly")


if __name__ == '__main__':
    scheduler = BlockingScheduler(timezone=utc)

    schedule_trades_for_year()

    # reschedule your trades for the future years ad infinitum
    scheduler.add_job(schedule_trades_for_year,
                      trigger=CronTrigger(month=1,
                                          day=1,
                                          hour=0,
                                          minute=0,
                                          timezone=utc))

    print('Press Ctrl+{0} to exit'.format('Break' if os.name == 'nt' else 'C'))

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
