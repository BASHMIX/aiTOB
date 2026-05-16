import httpx
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("STARTGG_API_TOKEN")

query = """
{
  __type(name: "Mutation") {
    fields {
      name
      args {
        name
        type {
          name
          kind
          ofType {
            name
            kind
          }
        }
      }
    }
  }
}
"""

def check():
    resp = httpx.post("https://api.start.gg/gql/alpha", 
                      json={"query": query}, 
                      headers={"Authorization": f"Bearer {token}"})
    if resp.status_code == 200:
        data = resp.json()
        fields = data.get("data", {}).get("__type", {}).get("fields", [])
        for f in fields:
            if f["name"] == "updateBracketSet":
                print("Args for updateBracketSet:")
                for arg in f["args"]:
                    print(f"  - {arg['name']}")
    else:
        print(f"Error: {resp.status_code}")

if __name__ == "__main__":
    check()
