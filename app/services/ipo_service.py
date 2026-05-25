import requests

def getIPOEvents():
    """
    Fetch IPO data from your API / DB / external source
    Replace URL with your real IPO endpoint
    """

    try:
        res = requests.get("http://localhost:3000/ipo-events")

        if res.status_code == 200:
            return res.json()

        return []

    except Exception as e:
        print("IPO fetch error:", str(e))
        return []