from playwright.sync_api import sync_playwright
import time
import json

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        api_responses = []

        def handle_response(response):
            if "rest/" in response.url and response.status == 200:
                try:
                    data = response.json()
                    print("Intercepted API:", response.url, "| Items:", len(data))
                    with open('sre_api_dump.json', 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False)
                except:
                    pass

        page.on("response", handle_response)
        
        print("Navigating...")
        page.goto("https://web.cvm.gov.br/app/sre-publico/#/consulta-oferta-publica")
        time.sleep(3)
        
        print("Clicking search...")
        # the filter button class is typically btn-primary or similar.
        # I'll just click the button with text 'Filtrar'
        page.click("button:has-text('Filtrar')")
        
        print("Waiting for results...")
        time.sleep(5)
        browser.close()

if __name__ == '__main__':
    run()
