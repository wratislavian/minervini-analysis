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
amerykanskie_spolki = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA',
    'META', 'NVDA', 'BRK-B', 'JNJ', 'V','LLY','WMT','JPM','UNH','AVGO','XOM'
]
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

def sprawdz_kryteria_minerviniego(df, ticker):
    # Obliczanie wskaźników tylko na dniach handlowych
    df['SMA_50'] = oblicz_sma(df, 50)
    df['SMA_150'] = oblicz_sma(df, 150)
    df['SMA_200'] = oblicz_sma(df, 200)
    df['52_tyg_min'] = df['Close'].rolling(window=252, min_periods=252).min()
    df['52_tyg_max'] = df['Close'].rolling(window=252, min_periods=252).max()

    # Usunięcie wierszy z brakującymi wartościami
    df = df.dropna(subset=['SMA_50', 'SMA_150', 'SMA_200', '52_tyg_min', '52_tyg_max']).copy()

    if df.empty:
        return None

    # Kryteria
    kryterium_1 = (df['SMA_50'] > df['SMA_150']) & (df['SMA_50'] > df['SMA_200'])
    kryterium_2 = df['SMA_150'] > df['SMA_200']
    kryterium_3 = (df['Close'] > df['SMA_50']) & (df['Close'] > df['SMA_150']) & (df['Close'] > df['SMA_200'])
    kryterium_4 = df['Close'] > df['52_tyg_min'] * 1.3
    kryterium_5 = df['Close'] >= df['52_tyg_max'] * 0.75

    # Sumowanie spełnionych kryteriów
    kryteria_splnione = kryterium_1.astype(int) + kryterium_2.astype(int) + kryterium_3.astype(int) + kryterium_4.astype(int) + kryterium_5.astype(int)

    # Ocena według liczby spełnionych kryteriów
    df['minervini_ocena'] = 'czerwona'
    df.loc[kryteria_splnione == 4, 'minervini_ocena'] = 'żółta'
    df.loc[kryteria_splnione == 5, 'minervini_ocena'] = 'zielona'

    return df[['minervini_ocena']].copy()

# Przetwarzanie wszystkich aktywów
wszystkie_oceny = []
for ticker, df in dane.items():
    print(f"Przetwarzam dane dla {ticker}...")
    df_oceny = sprawdz_kryteria_minerviniego(df, ticker)
    if df_oceny is not None:
        df_oceny['Ticker'] = ticker
        df_oceny = df_oceny.reset_index().rename(columns={'index': 'Date'})
        wszystkie_oceny.append(df_oceny)
    else:
        print(f"Brak wystarczających danych dla {ticker}.")

if not wszystkie_oceny:
    print("Brak danych do przetworzenia.")
    exit()

print("Wskaźniki obliczone.")

# Łączenie ocen w jeden DataFrame
oceny_df = pd.concat(wszystkie_oceny)
oceny_df['Date'] = pd.to_datetime(oceny_df['Date']).dt.strftime('%Y-%m-%d')

# Filtrowanie danych do ostatnich 6 miesięcy
start_date_six_months_ago = (dzisiaj - timedelta(days=180)).strftime('%Y-%m-%d')
oceny_df = oceny_df[oceny_df['Date'] >= start_date_six_months_ago]

# Pivot tabeli
tabela_pivot = oceny_df.pivot(index='Ticker', columns='Date', values='minervini_ocena')
tabela_pivot = tabela_pivot.reset_index()

# Odwrócenie kolejności kolumn
date_columns = tabela_pivot.columns.tolist()
date_columns.remove('Ticker')
date_columns_reversed = date_columns[::-1]
tabela_pivot = tabela_pivot[['Ticker'] + date_columns_reversed]

# Sortowanie
najnowsza_data = tabela_pivot.columns[1]  # Pierwsza kolumna z datą po odwróceniu
tabela_pivot['sort_key'] = tabela_pivot[najnowsza_data].map({'zielona': 0, 'żółta': 1, 'czerwona': 2, 'brak': 3})
tabela_pivot = tabela_pivot.sort_values(by='sort_key').drop('sort_key', axis=1)

# Przygotowanie danych do wykresów
pelne_daty = pd.date_range(start=start_date_six_months_ago, end=dzisiaj, freq='D')
pelne_daty_str = pelne_daty.strftime('%Y-%m-%d')

tabela_transponowana = tabela_pivot.set_index('Ticker').T
tabela_transponowana.index.name = 'Date'
tabela_transponowana = tabela_transponowana.reindex(pelne_daty_str)
tabela_transponowana = tabela_transponowana.ffill().bfill()

# Odwrócenie indeksów do porządku chronologicznego
tabela_transponowana = tabela_transponowana.iloc[::-1]

s
