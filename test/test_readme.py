from enum import Enum
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
    def __init__(self, src):
        self.name = src['name']
        self.description = src['weather']['description']
        self.temperature = src['main']['temp']
        # ...

class OpenWeather(WebAPI):
    base_url = 'https://api.openweathermap.org/data/2.5'

    def __init__(self, api_key: str):
        super().__init__(UrlApiKey('appid', api_key))

    async def city(self,  location: str, mode: Mode=Mode.JSON,
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