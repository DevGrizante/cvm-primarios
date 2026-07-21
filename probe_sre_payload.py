from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        def handle_request(request):
            if "rest/sitePublico/pesquisar/detalhado" in request.url:
                print("API Called with method:", request.method)
                print("Headers:", request.headers)
                print("Post Data:", request.post_data)

        page.on("request", handle_request)
        
        print("Navigating...")
        page.goto("https://web.cvm.gov.br/app/sre-publico/#/consulta-oferta-publica")
        time.sleep(3)
        
        print("Clicking search...")
        page.click("button:has-text('Filtrar')")
        
        time.sleep(5)
        browser.close()

if __name__ == '__main__':
    run()
