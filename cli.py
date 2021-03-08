import asyncio

from furaffinity_scrape import main

if __name__ == "__main__":
    m = main.Main()
    asyncio.run(m.run(), debug=False)
