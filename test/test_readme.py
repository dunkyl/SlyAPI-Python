from enum import Enum
import sys
from typing import Any

import pytest

from SlyAPI import *

class Mode(Enum):
    XML  = 'xml'
    HTML = 'html'
    JSON = None

class Units(Enum):
    STANDARD = 'standard' # Kelvin
    METRIC   = 'metric'
    IMPERIAL = 'imperial'

class City:
    def __init__(self, src: dict[str, Any]):
        self.name = src['name']
        self.description = src['weather'][0]['description']
        self.temperature = src['main']['temp']
        # ...

class OpenWeather(WebAPI):
    base_url = 'https://api.openweathermap.org/data/2.5'

    def __init__(self, api_key: str):
        super().__init__(UrlApiKey('appid', api_key))

    async def city(self, location: str, mode: Mode=Mode.JSON,
            units: Units=Units.STANDARD,
            lang: str|None = None) -> City:
        '''Get the current weather of a city.
           Location format: `City,State,Country`
           where State and Country are ISO3166 codes. '''
        params = {
            'q': location,
            'lang': lang,
            'units': units,
            'mode': mode,
        }
        return City(await self.get_json('/weather', params))

async def test_make_webapi():
    api = OpenWeather('example_key')
    assert api.base_url == 'https://api.openweathermap.org/data/2.5'

# Preconditions:
# - cwd is the project root
# - internet connection
# - API key for openweather.org is stored in test/apikey.txt
# Skipped by default unless run in debugger
@pytest.mark.skipif(sys.gettrace() is None, reason="Does side effects (web request)")
async def test_readme():

    key = open('test/apikey.txt', encoding='utf8').read().strip()
    weather = OpenWeather(key)

    city = await weather.city('New York,NY,US', units=Units.IMPERIAL)

    print(F"It's {city.temperature}°F in {city.name}, {city.description}.")

    assert city.name == 'New York'