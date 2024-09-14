import yfinance as yf
import pandas as pd
import os
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
    'META', 'NVDA', 'BRK-B', 'JNJ', 'V', 'MSTR'
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
    """Sprawdza, czy dane dla tickera są aktualne i w razie potrzeby je pobiera."""
    plik = f'{ticker}_data.csv'
    if os.path.exists(plik):
        # Odczyt istniejących danych
        df = pd.read_csv(plik, index_col=0, parse_dates=True)
        # Sprawdzenie ostatniej dostępnej daty
        ostatnia_data = df.index[-1]
        if ostatnia_data.date() >= (dzisiaj - timedelta(days=1)).date():
            print(f"Dane dla {ticker} są aktualne.")
            return df
        else:
            # Pobranie nowych danych od ostatniej daty do dzisiaj
            start = (ostatnia_data + timedelta(days=1)).strftime('%Y-%m-%d')
            end = dzisiaj.strftime('%Y-%m-%d')
            print(f"Aktualizuję dane dla {ticker} od {start} do {end}...")
            nowe_dane = pobierz_dane(ticker, start, end)
            if nowe_dane is not None:
                df = pd.concat([df, nowe_dane])
                df = df[~df.index.duplicated(keep='last')]
                df.sort_index(inplace=True)
                df.to_csv(plik)
            return df
    else:
        # Pobranie pełnych danych od start_date do dzisiaj
        print(f"Pobieram dane dla {ticker} od {start_date.strftime('%Y-%m-%d')} do {dzisiaj.strftime('%Y-%m-%d')}...")
        df = pobierz_dane(ticker, start_date.strftime('%Y-%m-%d'), dzisiaj.strftime('%Y-%m-%d'))
        if df is not None:
            df.to_csv(plik)
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

    # Zapisanie wszystkich obliczeń do CSV
    df_do_zapisu = df[['Close', 'SMA_50', 'SMA_150', 'SMA_200', '52_tyg_min', '52_tyg_max', 'minervini_ocena']]
    df_do_zapisu.to_csv(f"{ticker}_obliczenia.csv")

    return df[['minervini_ocena']].copy()

# Przetwarzanie wszystkich aktywów
wszystkie_oceny = []
for ticker, df in dane.items():
    print(f"Przetwarzam dane dla {ticker}...")
    # Brak reindeksacji przed obliczeniami
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

suma_kategorii = pd.DataFrame(index=tabela_transponowana.index)
for ocena in ['zielona', 'żółta', 'czerwona']:
    suma_kategorii[ocena] = (tabela_transponowana == ocena).sum(axis=1)

def tworzenie_wykresu(suma_kategorii, tytul, nazwa_pliku):
    plt.figure(figsize=(12, 6))
    dates = pd.to_datetime(suma_kategorii.index)
    for ocena, kolor in zip(['zielona', 'żółta', 'czerwona'], ['green', 'orange', 'red']):
        plt.plot(dates, suma_kategorii[ocena], label=ocena.capitalize(), color=kolor)
    plt.xlabel('Data')
    plt.ylabel('Liczba aktywów')
    plt.title(tytul)
    plt.legend()
    plt.gca().xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.gca().yaxis.set_major_locator(MaxNLocator(integer=True))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(nazwa_pliku)
    plt.close()

# Tworzenie wykresu ogólnego
tworzenie_wykresu(suma_kategorii, 'Trend liczby aktywów w poszczególnych kategoriach (Ogółem)', 'trend.png')

# Tworzenie wykresów dla każdej grupy
for nazwa_grupy, lista_aktywow in grupy_aktywow.items():
    tabela_transponowana_grupy = tabela_transponowana[lista_aktywow]
    suma_kategorii_grupy = pd.DataFrame(index=tabela_transponowana_grupy.index)
    for ocena in ['zielona', 'żółta', 'czerwona']:
        suma_kategorii_grupy[ocena] = (tabela_transponowana_grupy == ocena).sum(axis=1)
    nazwa_pliku = f"trend_{nazwa_grupy.replace(' ', '_').lower()}.png"
    tworzenie_wykresu(suma_kategorii_grupy, f'Trend liczby aktywów ({nazwa_grupy})', nazwa_pliku)

# Generowanie HTML
szablon_html = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Wyniki Analizy Minerviniego</title>
    <style>
        table { border-collapse: collapse; }
        th, td { border: 1px solid #ccc; padding: 5px; text-align: center; }
        .zielona { color: green; }
        .żółta { color: orange; }
        .czerwona { color: red; }
        .brak { color: grey; }
    </style>
</head>
<body>
    <h1>Wyniki Analizy Minerviniego</h1>
    <table>
        <tr>
            <th>Aktywo</th>
            {% for data in daty %}
                <th>{{ data }}</th>
            {% endfor %}
        </tr>
        {% for row in tabela %}
        <tr>
            <td>{{ row['Ticker'] }}</td>
            {% for data in daty %}
                {% set ocena = row.get(data, 'brak') %}
                <td class="{{ ocena }}">
                    {% if ocena != 'brak' %}
                        &#9679;
                    {% else %}
                        -
                    {% endif %}
                </td>
            {% endfor %}
        </tr>
        {% endfor %}
    </table>
    <h2>Trend liczby aktywów w poszczególnych kategoriach (Ogółem)</h2>
    <img src="trend.png" alt="Wykres trendu ogólnego">
    {% for nazwa_grupy in grupy_nazwy %}
        <h2>Trend liczby aktywów ({{ nazwa_grupy }})</h2>
        <img src="trend_{{ nazwa_grupy.replace(' ', '_').lower() }}.png" alt="Wykres trendu {{ nazwa_grupy }}">
    {% endfor %}
</body>
</html>
'''

# Przygotowanie listy dat (już odwróconej)
daty = tabela_pivot.columns[1:].tolist()  # Pomijamy 'Ticker'

tabela = tabela_pivot.to_dict(orient='records')
grupy_nazwy = list(grupy_aktywow.keys())

env = Environment(loader=FileSystemLoader('.'))
template = env.from_string(szablon_html)
html_output = template.render(daty=daty, tabela=tabela, grupy_nazwy=grupy_nazwy)

with open('wyniki_minervini.html', 'w', encoding='utf-8') as f:
    f.write(html_output)

print("Plik HTML został wygenerowany jako 'wyniki_minervini.html'.")
