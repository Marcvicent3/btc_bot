from news_scraper import get_bitcoin_headlines
from translator import translate_to_spanish

headlines = get_bitcoin_headlines()
print("Últimos titulares de Bitcoin (en inglés):")
for h in headlines:
    print("-", h)

translated = translate_to_spanish(headlines)
print("\nTitulares traducidos:")
for h in translated:
    print("-", h)
