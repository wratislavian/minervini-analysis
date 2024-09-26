import yfinance as yf
import pandas as pd
import numpy as np
import os
from datetime import timedelta
import matplotlib.pyplot as plt
import logging

# Ustawienie konfiguracji logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Normalizacja dzisiejszej daty
dzisiaj = pd.Timestamp.today().normalize()
start_date = dzisiaj - timedelta(days=450)  # Około 15 miesięcy

# Lista aktywów
polskie_spolki = ['PKN.WA', 'PZU.WA', 'KGH.WA', 'PEO.WA', 'PKO.WA', 'LPP.WA', 'DNP.WA', 'CDR.WA', 'ALR.WA', 'MRC.WA']
amerykanskie_spolki = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'BRK-B', 'JNJ', 'V']
metale_szlachetne = ['GC=F', 'SI=F', 'PL=F', 'PA=F']
surowce = ['CL=F', 'NG=F', 'BZ=F', 'HG=F']
kryptowaluty = ['BTC-USD', 'ETH-USD', 'XRP-USD', 'ADA-USD', 'DOGE-USD']

aktywa = polskie_spolki + amerykanskie_spolki + metale_szlachetne + surowce + kryptowaluty

def pobierz_dane(ticker, interval='1d', start=None):
    """
    Pobiera dane dla podanego tickera z Yahoo Finance.

    Parametry:
    ticker (str): Symbol aktywa.
    interval (str): Interwał danych (domyślnie '1d' - dzienny).
    start (str): Data początkowa w formacie 'YYYY-MM-DD'.

    Zwraca:
    DataFrame: Dane pobrane dla danego tickera.
    """
    try:
        if start:
            df = yf.download(ticker, start=start, end=dzisiaj.strftime('%Y-%m-%d'), interval=interval)
        else:
            df = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), end=dzisiaj.strftime('%Y-%m-%d'), interval=interval)
        if df.empty:
            logging.warning(f"Brak danych dla {ticker}. Ticker może być niedostępny.")
            return None
        else:
            # Usunięcie dzisiejszego dnia z danych
            df = df[df.index < dzisiaj]
            return df
    except Exception as e:
        logging.error(f"Błąd podczas pobierania danych dla {ticker}: {e}")
        return None

def aktualizuj_dane(ticker):
    """
    Aktualizuje dane dla podanego tickera, zapisując je do pliku CSV.

    Parametry:
    ticker (str): Symbol aktywa.

    Zwraca:
    DataFrame: Zaktualizowane dane dla danego tickera.
    """
    plik = f'{ticker}_data.csv'
    if os.path.exists(plik):
        df = pd.read_csv(plik, index_col=0, parse_dates=True)
        ostatnia_data = df.index[-1].normalize()
        if ostatnia_data >= dzisiaj:
            logging.info(f"Dane dla {ticker} są aktualne.")
            return df
        else:
            logging.info(f"Aktualizuję dane dla {ticker} od {ostatnia_data.strftime('%Y-%m-%d')}...")
            nowe_dane = pobierz_dane(ticker, start=ostatnia_data.strftime('%Y-%m-%d'))
            if nowe_dane is not None:
                df = pd.concat([df, nowe_dane])
                df = df[~df.index.duplicated(keep='last')]
                df.sort_index(inplace=True)
                df.to_csv(plik)
            else:
                logging.warning(f"Brak nowych danych dla {ticker}.")
    else:
        logging.info(f"Pobieram dane dla {ticker}...")
        df = pobierz_dane(ticker)
        if df is not None:
            df.to_csv(plik)
        else:
            logging.warning(f"Brak danych dla {ticker}.")
    return df

def oblicz_sma(df, okres):
    """
    Oblicza średnią kroczącą (SMA) dla podanego okresu.

    Parametry:
    df (DataFrame): Dane zawierające kolumnę 'Close'.
    okres (int): Okres dla średniej kroczącej.

    Zwraca:
    Series: Średnia krocząca.
    """
    return df['Close'].rolling(window=okres).mean()

def sprawdz_kryteria_minerviniego(df):
    """
    Sprawdza kryteria Minerviniego dla podanego DataFrame.

    Parametry:
    df (DataFrame): Dane zawierające kolumnę 'Close'.

    Zwraca:
    DataFrame: Dane z dodaną kolumną 'minervini_ocena'.
    """
    df['SMA_50'] = oblicz_sma(df, 50)
    df['SMA_150'] = oblicz_sma(df, 150)
    df['SMA_200'] = oblicz_sma(df, 200)

    df['52_tyg_min'] = df['Close'].rolling(window=252).min()
    df['52_tyg_max'] = df['Close'].rolling(window=252).max()

    # Usunięcie wierszy z brakującymi wartościami
    df = df.dropna(subset=['SMA_50', 'SMA_150', 'SMA_200', '52_tyg_min', '52_tyg_max']).copy()

    # Kryteria Minerviniego
    kryterium_1 = (df['SMA_50'] > df['SMA_150']) & (df['SMA_50'] > df['SMA_200'])
    kryterium_2 = df['SMA_150'] > df['SMA_200']
    kryterium_3 = (df['Close'] > df['SMA_50']) & (df['Close'] > df['SMA_150']) & (df['Close'] > df['SMA_200'])
    kryterium_4 = df['Close'] > df['52_tyg_min'] * 1.3
    kryterium_5 = df['Close'] >= df['52_tyg_max'] * 0.75

    # Sumowanie spełnionych kryteriów
    kryteria_splnione = (
        kryterium_1.astype(int) +
        kryterium_2.astype(int) +
        kryterium_3.astype(int) +
        kryterium_4.astype(int) +
        kryterium_5.astype(int)
    )

    # Dodanie kolumny z oceną -1 lub +1
    df['minervini_ocena'] = np.where(kryteria_splnione == 5, 1, -1)

    return df

def oblicz_srednia_ocene(dane):
    """
    Oblicza średnią ocenę aktywów dla każdego dnia.

    Parametry:
    dane (dict): Słownik z DataFrames dla każdego tickera.

    Zwraca:
    Series: Średnia ocena dla każdego dnia.
    """
    df_oceny = pd.DataFrame()

    for ticker, df in dane.items():
        df_oceny[ticker] = df['minervini_ocena']

    # Uzupełnienie brakujących wartości
    df_oceny.fillna(0, inplace=True)

    # Obliczenie średniej oceny dla każdego dnia
    df_oceny['srednia'] = df_oceny.mean(axis=1, skipna=True)
    return df_oceny['srednia']

def generuj_wykres_trendu(dane, nazwa_pliku, aktywa_lista=None):
    """
    Generuje wykres trendu cenowego dla podanych danych.

    Parametry:
    dane (dict): Słownik z DataFrames dla każdego tickera.
    nazwa_pliku (str): Nazwa pliku, do którego zapisany zostanie wykres.
    aktywa_lista (list): Lista tickerów do uwzględnienia w wykresie.

    Zwraca:
    None
    """
    plt.figure(figsize=(12, 8))
    if aktywa_lista is None:
        aktywa_lista = dane.keys()
    for ticker in aktywa_lista:
        df = dane[ticker]
        df['Close'].plot(label=ticker)
    plt.title('Trend cenowy aktywów')
    plt.ylabel('Cena zamknięcia')
    plt.xlabel('Data')
    plt.legend()
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(nazwa_pliku)
    plt.close()

def zapisz_wyniki_do_html(dane, nazwa_pliku):
    """
    Zapisuje wyniki analizy do pliku HTML.

    Parametry:
    dane (dict): Słownik z DataFrames dla każdego tickera.
    nazwa_pliku (str): Nazwa pliku HTML.

    Zwraca:
    None
    """
    with open(nazwa_pliku, 'w', encoding='utf-8') as f:
        f.write('<html><head><meta charset="UTF-8"></head><body>')
        f.write('<h1>Wyniki analizy Minerviniego</h1>')
        for ticker, df in dane.items():
            ostatni_wiersz = df.tail(1)
            f.write(f'<h2>{ticker}</h2>')
            f.write(ostatni_wiersz.to_html())
        f.write('</body></html>')

if __name__ == "__main__":
    # Pobranie i aktualizacja danych
    dane = {}
    for ticker in aktywa:
        df = aktualizuj_dane(ticker)
        if df is not None:
            dane[ticker] = df

    logging.info("Dane pobrane i zapisane do plików CSV.")

    # Przetwarzanie danych i sprawdzanie kryteriów Minerviniego
    for ticker, df in dane.items():
        logging.info(f"Sprawdzam kryteria dla {ticker}...")
        dane[ticker] = sprawdz_kryteria_minerviniego(df)

    logging.info("Wskaźniki obliczone, kryteria Minerviniego sprawdzone.")

    # Oblicz średnią ocenę dla wszystkich aktywów
    srednia_ocena = oblicz_srednia_ocene(dane)

    # Wykres średniej oceny
    plt.figure(figsize=(10, 6))
    srednia_ocena.plot()
    plt.title('Średnia ocena aktywów według kryteriów Minerviniego')
    plt.ylabel('Średnia ocena (+1 lub -1)')
    plt.xlabel('Data')
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('srednia_ocena_aktywow.png')
    plt.close()

    # Generowanie wykresów trendów dla różnych grup aktywów
    generuj_wykres_trendu(dane, 'trend.png')

    # Wykresy dla poszczególnych grup
    generuj_wykres_trendu(dane, 'trend_akcje_pl.png', polskie_spolki)
    generuj_wykres_trendu(dane, 'trend_akcje_us.png', amerykanskie_spolki)
    generuj_wykres_trendu(dane, 'trend_surowce.png', surowce + metale_szlachetne)
    generuj_wykres_trendu(dane, 'trend_kryptowaluty.png', kryptowaluty)

    # Zapisanie wyników do pliku HTML
    zapisz_wyniki_do_html(dane, 'wyniki_minervini.html')

    logging.info("Wszystkie wykresy i raporty zostały wygenerowane.")
