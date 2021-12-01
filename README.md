# ![sly logo](https://raw.githubusercontent.com/dunkyl/SlyMeta/main/sly%20logo.svg) SlyAPI for Python

> 🚧 **This library is an early work in progress! Breaking changes may be frequent.**

> 🐍 For Python 3.10+

No-boilerplate, async and typed web api access with oauth1/2.

```shell
pip install slyapi
```

Meant as a foundation for other libraries more than being used directly. It is used by my more specific libraries:

* [SlyYTDAPI](https://github.com/dunkyl/SlyPyYTDAPI) and [SlyYTAAPI](https://github.com/dunkyl/SlyPyYTAAPI): for the YouTube APIs
* [SlyTwitter](https://github.com/dunkyl/SlyPyTwitter)
* [SlySheets](https://github.com/dunkyl/SlyPySheets): for Google Sheets

This library does not provide full coverage of OAuth1 or OAuth2, particularly it does not support the device code flow, nor the legacy implicit flow. Since it is intended to interface with 3rd party APIs, it does not implement the password flow.

---

Example library usage:

```py
from SlyAPI import *

class Mode(EnumParam):
    XML  = 'xml'
    HTML = 'html'
    JSON = None

class Units(EnumParam):
    STANDARD = 'standard'
    METRIC = 'metric'
    IMPERIAL = 'imperial'

class City:
    def __init__(self, src):
        self.name = src['name']
        self.description = src['weather']['description']
        self.temperature = src['main']['temp']
        # ...

class OpenWeather(WebAPI):
    base_url = 'https://api.openweathermap.org/data/2.5'

    async def _async_init(self, api_key: str):
        await super()._async_init(APIKey('appid', api_key))
        
    async def city(self, 
        where: str,
        mode: Mode=Mode.JSON,
        units: Units=Units.METRIC,
        lang: str = None) -> City:
        '''
            Get the current weather of a city.
            Location format: `City,State,Country`
            where State and Country are ISO3166 codes.
        '''
        params = {
            **(mode+units).to_dict(),
            'q': where,
            'lang': lang
        }
        return City(await self.get_json('/weather', param))

    # ...
```
