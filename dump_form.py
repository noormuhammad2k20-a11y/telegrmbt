import httpx
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

with httpx.Client(headers=headers, follow_redirects=True) as client:
    r = client.get("https://quotex.io/pt/sign-in/modal/")
    print(r.status_code, r.url)
    soup = BeautifulSoup(r.text, 'html.parser')
    for form in soup.find_all("form"):
        print("Form action:", form.get("action"))
        for inp in form.find_all("input"):
            print(f"  Input: name={inp.get('name')}, type={inp.get('type')}, value={inp.get('value')}")
