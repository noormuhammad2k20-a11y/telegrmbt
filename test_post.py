import asyncio
from pyquotex.api import QuotexAPI
from pyquotex.network.login import Login

async def test_post():
    api = QuotexAPI(host="quotex.io", username="u", password="p", lang="pt")
    login = Login(api)
    
    await login.get_sign_page()
    await login.send_request("GET", f"{login.full_url}/sign-in/modal/")
    html = login.get_soup()
    
    token = html.find("input", {"name": "_token"}).get("value")
    
    data = {
        "_token": token,
        "email": "test@example.com",
        "password": "password",
        "remember": 1,
    }
    
    # Try POST to /sign-in/
    resp1 = await login.send_request("POST", f"{login.full_url}/sign-in/", data=data)
    print("POST /sign-in/ URL:", resp1.url)
    print("POST /sign-in/ Status:", resp1.status_code)
    
    # Reset cookies/token
    await login.get_sign_page()
    await login.send_request("GET", f"{login.full_url}/sign-in/modal/")
    html2 = login.get_soup()
    token2 = html2.find("input", {"name": "_token"}).get("value")
    data["_token"] = token2
    
    # Try POST to /sign-in/modal/
    resp2 = await login.send_request("POST", f"{login.full_url}/sign-in/modal/", data=data)
    print("POST /sign-in/modal/ URL:", resp2.url)
    print("POST /sign-in/modal/ Status:", resp2.status_code)

if __name__ == "__main__":
    asyncio.run(test_post())
