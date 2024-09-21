import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from jinja2 import Environment, FileSystemLoader
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import matplotlib.dates as mdates

# Lista aktywów
polskie_spolki = [
    'PKN.WA', 'PZU.WA', 'KGH.WA', 'PEO.WA', 'PKO.WA',
    'LPP.WA', 'DNP.WA', 'CDR.WA', 'ALR.WA', 'MRC.WA'
]
amerykanskie_spolki = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'BRK-B', 'JNJ', 'V', 'LLY', 'AVGO', 'WMT', 'JPM', 'UNH']
metale_szlachetne = ['GC=F', 'SI=F', 'PL=F', 'PA=F']
surowce = ['CL=F', 'NG=F', 'BZ=F', 'HG=F']
kryptowaluty = ['BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'ADA-USD']

aktywa = polskie_spolki + amerykanskie_spolki + metale_szlachetne + surowce + kryptowaluty

# Definicja grup aktywów
grupy_aktywow = {
    'Akcje US': amerykanskie_spolki,
    'Akcje PL': polskie_spolki,
    'Kryptowaluty': kryptowaluty,
    'Surowce': metale_szlachetne + surowce
}

# Ustawienie dat
dzisiaj = datetime.today()
start_date = dzisiaj - timedelta(days=5*365)  # Około 5 lat

def pobierz_dane(ticker, start, end):
    """Pobiera dane dla danego tickera."""
    try:
        df = yf.download(
            ticker,
            start=start,
            end=end,
            interval='1d'
        )
        if df.empty:
            print(f"Brak danych dla {ticker}.")
            return None
        return df
    except Exception as e:
        print(f"Błąd podczas pobierania danych dla {ticker}: {e}")
        return None

def aktualizuj_dane(ticker):
    """Pobiera dane dla tickera."""
    print(f"Pobieram dane dla {ticker} od {start_date.strftime('%Y-%m-%d')} do {dzisiaj.strftime('%Y-%m-%d')}...")
    
    # Sprawdzenie, czy aktywo to kryptowaluta
    czy_krypto = ticker in kryptowaluty
    
    # Sprawdzenie, czy dziś jest weekend (sobota lub niedziela)
    dzien_tygodnia = dzisiaj.weekday()
    if dzien_tygodnia >= 5 and not czy_krypto:
        print(f"Dziś jest weekend i {ticker} nie jest kryptowalutą. Pomijam pobieranie danych.")
        return None
    
    df = pobierz_dane(ticker, start_date.strftime('%Y-%m-%d'), dzisiaj.strftime('%Y-%m-%d'))
    return df

# Pobieranie danych dla wszystkich aktywów
dane = {}
for ticker in aktywa:
    df = aktualizuj_dane(ticker)
    if df is not None:
        dane[ticker] = df
    else:
        print(f"Brak danych dla {ticker}, pomijam.")

print("Dane pobrane.")

def oblicz_sma(df, okres):
    return df['Close'].rolling(window=okres, min_periods=okres).mean()

def sprawdz_kryteria_minerviniego(df, ticker, czy_krypto):
    # Dostosowanie okresów dla kryptowalut
    if czy_krypto:
        # Przelicznik dni kalendarzowych na dni handlowe dla kryptowalut (365 dni w roku)
        mnoznik = 365 / 252  # Około 1.45
        sma_50_okres = int(50 * mnoznik)
        sma_150_okres = int(150 * mnoznik)
        sma_200_okres = int(200 * mnoznik)
        tyg52_okres = int(252 * mnoznik)
    else:
        sma_50_okres = 50
        sma_150_okres = 150
        sma_200_okres = 200
        tyg52_okres = 252

    # Obliczanie wskaźników
    df['SMA_50'] = oblicz_sma(df, sma_50_okres)
    df['SMA_150'] = oblicz_sma(df, sma_150_okres)
    df['SMA_200'] = oblicz_sma(df, sma_200_okres)
    df['52_tyg_min'] = df['Close'].rolling(window=tyg52_okres, min_periods=tyg52_okres).min()
    df['52_tyg_max'] = df['Close'].rolling(window=tyg52_okres, min_periods=tyg52_okres).max()

    # Usunięcie wierszy z brakującymi wartościami
    df = df.dropna(subset=['SMA_50', 'SMA_150', 'SMA_200', '52_tyg_min', '52_tyg_max']).copy()

    if df.empty:
        return None

    # Kryteria
    kryterium_1 = (df['SMA_50'] > df['SMA_150']) & (df['SMA_50'] > df['SMA_200'])
    kryterium_2 = df['SMA_150'] > df['SMA_200']
    kryterium_3 = (df['Close'] > df['SMA_50']) & (df['Close'] > 
