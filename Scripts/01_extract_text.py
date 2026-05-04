import os
import re
import pandas as pd
import fitz
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_CSV = os.path.join(BASE_DIR, "Data", "links.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "Data", "raw_txt")


def clean_spaces(text):
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_text_from_pdf(content):
    pdf = fitz.open(stream=content, filetype="pdf")
    text_parts = []
    for page in pdf:
        text_parts.append(page.get_text())
    return clean_spaces(" ".join(text_parts))


def extract_text_from_html(html):
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    main = soup.find("main")
    if main:
        text = main.get_text(separator=" ")
    else:
        text = soup.get_text(separator=" ")

    return clean_spaces(text)


def create_driver():
    options = Options()
    options.add_argument("--headless")           # Sin ventana visible
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def extract_text(driver, url):
    if url.lower().endswith(".pdf"):
        import requests
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return extract_text_from_pdf(response.content)

    driver.get(url)
    html = driver.page_source
    return extract_text_from_html(html)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df = pd.read_csv(INPUT_CSV, encoding="latin-1")

    driver = create_driver()

    try:
        for _, row in df.iterrows():
            doc_id = row["id"]
            title = row["title"]
            url = row["url"]

            print(f"Extrayendo documento {doc_id}: {title}")

            try:
                text = extract_text(driver, url)

                output_path = os.path.join(OUTPUT_DIR, f"{doc_id}.txt")
                with open(output_path, "w", encoding="utf-8") as file:
                    file.write(text)

                print(f"Guardado: {output_path}")
                print(f"Palabras aproximadas: {len(text.split())}")

            except Exception as error:
                print(f"Error con documento {doc_id}: {error}")

    finally:
        driver.quit()  # Siempre cierra el navegador al terminar


if __name__ == "__main__":
    main()