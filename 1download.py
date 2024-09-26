import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

# Lista aktywów
polskie_spolki = ['PKN.WA', 'PZU.WA', 'KGH.WA', 'PEO.WA', 'PKO.WA', 'LPP.WA', 'DNP.WA', 'CDR.WA', 'ALR.WA', 'MRC.WA']
amerykanskie_spolki = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'BRK-B', 'JNJ', 'V']
metale_szlachetne = ['GC=F', 'SI=F', 'PL=F', 'PA=F']
surowce = ['CL=F', 'NG=F', 'BZ=F', 'HG=F']
aktywa = polskie_spolki + amerykanskie_spolki + metale_szlachetne + surowce

# Ustawienie dat
dzisiaj = datetime.today()
start_date = dzisiaj - timedelta(days=450)  # Około 15 miesięcy

def pobierz_dane(ticker, interval='1d', start=None):
    try:
        if start:
            df = yf.download(ticker, start=start, end=dzisiaj.strftime('%Y-%m-%d'), interval=interval)
        else:
            df = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), end=dzisiaj.strftime('%Y-%m-%d'), interval=interval)
        if df.empty:
            print(f"Brak danych dla {ticker}. Ticker może być niedostępny.")
            return None
        else:
            # Usunięcie dzisiejszego dnia z danych
            df = df[df.index < dzisiaj]
            return df
    except Exception as e:
        print(f"Błąd podczas pobierania danych dla {ticker}: {e}")
        return None

def aktualizuj_dane(ticker):
    plik = f'{ticker}_data.csv'
    if os.path.exists(plik):
        df = pd.read_csv(plik, index_col=0, parse_dates=True)
        ostatnia_data = df.index[-1] + pd.Timedelta(days=1)
        if ostatnia_data.date() >= dzisiaj.date():
            print(f"Dane dla {ticker} są aktualne.")
            return df
        else:
            print(f"Aktualizuję dane dla {ticker} od {ostatnia_data.date()}...")
            nowe_dane = pobierz_dane(ticker, start=ostatnia_data.strftime('%Y-%m-%d'))
            if nowe_dane is not None:
                df = pd.concat([df, nowe_dane])
                df = df[~df.index.duplicated(keep='last')]
                df.sort_index(inplace=True)
                df.to_csv(plik)
    else:
        print(f"Pobieram dane dla {ticker}...")
        df = pobierz_dane(ticker)
        if df is not None:
            df.to_csv(plik)
    return df

dane = {}
for ticker in aktywa:
    df = aktualizuj_dane(ticker)
    if df is not None:
        dane[ticker] = df

print("Dane pobrane i zapisane do plików CSV.")

def oblicz_sma(df, okres):
    return df['Close'].rolling(window=okres).mean()

def sprawdz_kryteria_minerviniego(df):
    df['SMA_50'] = oblicz_sma(df, 50)
    df['SMA_150'] = oblicz_sma(df, 150)
    df['SMA_200'] = oblicz_sma(df, 200)
    
    df['52_tyg_min'] = df['Close'].rolling(window=252).min()
    df['52_tyg_max'] = df['Close'].rolling(window=252).max()

    # Usunięcie wierszy z brakującymi wartościami
    df = df.dropna(subset=['SMA_50', 'SMA_150', 'SMA_200', '52_tyg_min', '52_tyg_max'])
    df = df.copy()  # Upewniamy się, że pracujemy na kopii danych

    # Kryterium 1
    kryterium_1 = (df['SMA_50'] > df['SMA_150']) & (df['SMA_50'] > df['SMA_200'])
    
    # Kryterium 2
    kryterium_2 = df['SMA_150'] > df['SMA_200']
    
    # Kryterium 3
    kryterium_3 = (df['Close'] > df['SMA_50']) & (df['Close'] > df['SMA_150']) & (df['Close'] > df['SMA_200'])
    
    # Kryterium 4
    kryterium_4 = df['Close'] > df['52_tyg_min'] * 1.3
    
    # Kryterium 5
    kryterium_5 = df['Close'] >= df['52_tyg_max'] * 0.75

    # Sumowanie spełnionych kryteriów
    kryteria_splnione = (
        kryterium_1.astype(int) +
        kryterium_2.astype(int) +
        kryterium_3.astype(int) +
        kryterium_4.astype(int) +
        kryterium_5.astype(int)
    )
    
    # Dodanie kolumny z wynikami -1 lub +1
    df.loc[:, 'minervini_ocena'] = kryteria_splnione.apply(lambda x: 1 if x == 5 else -1)

    return df

# Funkcja do obliczania średniej oceny dla każdego dnia
def oblicz_srednia_ocene(dane):
    df_oceny = pd.DataFrame()
    
    for ticker, df in dane.items():
        df_oceny[ticker] = df['minervini_ocena']
    
    # Obliczenie średniej z każdej kolumny (średnia ocena dla każdego dnia)
    df_oceny['srednia'] = df_oceny.mean(axis=1)
    return df_oceny['srednia']

# Przykład dla wszystkich aktywów
for ticker, df in dane.items():
    print(f"Sprawdzam kryteria dla {ticker}...")
    dane[ticker] = sprawdz_kryteria_minerviniego(df)

print("Wskaźniki obliczone, kryteria Minerviniego sprawdzone.")

# Oblicz średnią ocene dla wszystkich aktywów
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
plt.show()
