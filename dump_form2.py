import asyncio
from pyquotex.api import QuotexAPI
from pyquotex.network.login import Login

async def dump_form():
    api = QuotexAPI(host="quotex.io", username="u", password="p", lang="pt")
    login = Login(api)
    
    # 1. Get sign page
    await login.get_sign_page()
    print("Full URL after get_sign_page:", login.full_url)
    
    # 2. Get modal
    await login.send_request("GET", f"{login.full_url}/sign-in/modal/")
    html = login.get_soup()
    
    # Dump forms
    for form in html.find_all("form"):
        print("Form action:", form.get("action"))
        for inp in form.find_all("input"):
            print(f"  Input: name={inp.get('name')}, type={inp.get('type')}, value={inp.get('value')}")

if __name__ == "__main__":
    asyncio.run(dump_form())
