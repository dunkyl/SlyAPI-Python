# ![sly logo](https://raw.githubusercontent.com/dunkyl/SlyMeta/main/sly%20logo%20py.svg) SlyAPI for Python

<!-- elevator begin -->

> 🐍 For Python 3.10+

No-boilerplate, async and typed web api access with oauth1/2. 😋

```sh
pip install slyapi
```

Meant as a foundation for other libraries more than being used directly. SlyAPI handles authorization and managing requests. It is used by my more specific libraries:

- [SlyYTDAPI](https://github.com/dunkyl/SlyYTDAPI-Python) and [SlyYTAAPI](https://github.com/dunkyl/SlyYTAAPI-Python): for the YouTube APIs
- [SlyTwitter](https://github.com/dunkyl/SlyTwitter-Python)
- [SlySheets](https://github.com/dunkyl/SlySheets-Python): for Google Sheets
- [SlyGmail](https://github.com/dunkyl/SlyGmail-Python)

There is also a version of this library available for F#/C#:

- [SlyAPI for F#](https://github.com/dunkyl/SlyAPI-FSharp)

This library does not provide full coverage of OAuth1 or OAuth2, particularly it does not support the device code flow, nor the legacy implicit flow. Since it is intended to interface with 3rd party APIs, it does not implement the password flow.

<!-- elevator end -->

---

Example CLI usage:

`py` may need to be replaced with `python3` on Linux or MacOS.
```sh
ls
#  ./my_cool_dev_app.py

py -m SlyAPI scaffold
#  ... (wizard run)
#  ./my_google_app.json

#  ... (credentials filled)

py -m SlyAPI grant
#  ... (wizard run)
#  ./oauth2_grant.json
```

Note that the libraries listed above implement a more specific wizard to each API.

---

Example library usage:

```py
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
        return City(await self.get_json('/weather', {
            'q': location,
            'lang': lang,
            'units': units,
            'mode': mode,
        }))
    # ...
```
