'''Authorization wizards for OAuth1 and OAuth2'''
import json
from dataclasses import asdict
import os
import sys
from typing import Callable, cast
import functools
import pick
import termcolor

from SlyAPI.web import JsonMap

from .oauth1 import OAuth1App, command_line_oauth1
from .oauth2 import F_Params, F_Return, OAuth2App, command_line_oauth2

async def grant_oauth1(app_file: str, out_file: str):
    app = OAuth1App.from_json_file(app_file)
    user = await command_line_oauth1(app, 'localhost', 8080, False)

    with open(out_file, 'w') as f: json.dump(asdict(user), f, indent=4)

async def grant_oauth2(app_file: str, out_file: str, scopes: list[str]):
    app = OAuth2App.from_json_file(app_file)
    user = await \
        command_line_oauth2(app, 'localhost', 8080, False, scopes)
    
    # to_dict used instead of asdict because OAuth2Yser has a datetime
    with open(out_file, 'w') as f: json.dump(user.to_dict(), f, indent=4)

def _get_available_scopes(scopesType: type):
    return [
        str(getattr(scopesType, name)) for name in dir(scopesType)
        if not name.startswith('_')
    ]

def pick_scopes(scopesType: type):
    sel_scopes = cast(list[tuple[str, int]], pick.pick( # type: ignore
        _get_available_scopes(scopesType),
        "Select one or more scopes to authorize:\n"
        "Arrows to move, Space to select, Enter to continue",
        multiselect=True
    ))
    scopes = [scope for (scope, _) in sel_scopes]
    print("Authorizing for the following scopes:")
    for scope in scopes:
        print(f"\t- {scope}")
    return scopes

# exit the program if the user presses Ctrl+C
def _crtlc_exit(fn: Callable[F_Params, F_Return]) -> Callable[F_Params, F_Return]:
    @functools.wraps(fn)
    def wrapped(*args: F_Params.args, **kwargs: F_Params.kwargs):
        try:
            return fn(*args, **kwargs)
        except KeyboardInterrupt:
            sys.exit(0)
    return wrapped

@_crtlc_exit
def _warn_gitignore(file: str):

    import shutil, subprocess
    if not shutil.which('git'): # is git available?
        return
    result = subprocess.Popen(['git', 'check-ignore', file],
                            stdout=subprocess.DEVNULL).wait()
    # result == 128 if file isn't in the repository, which is OK
    # result == 0 if file is in .gitignore
    if result == 1: # not in .gitignore
        termcolor.cprint(F"DANGER: '{file}' is not git-ignored!", "red")
        termcolor.cprint("Please ensure that this file is kept secret!", "red")
        input("Press Enter to acknowledge and continue.")

@_crtlc_exit
def _pick_app_file(check_exists: bool=True):
    print("Select a client/app credential JSON file to use:")
    print("If you don't have one, you can exit and create one with the 'scaffold' command.")
    app_file = input("App file: ")

    if not os.path.isfile(app_file) and check_exists:
        termcolor.cprint("App does not exist!", "red")
        sys.exit(1)
    _warn_gitignore(app_file)

    return app_file

@_crtlc_exit
def _pick_user_file():
    print("Select a user credential JSON file to output or overwrite:")
    user_file = input("User file: ")

    if os.path.isdir(user_file):
        termcolor.cprint("User file is a directory.", "red")
        sys.exit(1)
    elif os.path.exists(user_file):
        print("User file already exists. Overwrite? (y/n)")
        overwrite = input("> ").lower()
        if overwrite != 'y':
            sys.exit(0)
    _warn_gitignore(user_file)

    return user_file

def scaffold_oauth1(file: str, override: JsonMap|None=None): 
    with open(file, 'w') as f:
        json.dump({
        'key': '',
        'secret': '',
        'request_uri': '',
        'authorize_uri': '',
        'access_uri': ''
    }|(override or {}), f, indent=4)

def scaffold_oauth2(file: str, override: JsonMap|None=None):
    with open(file, 'w') as f:
        json.dump({
            'id': '',
            'secret': '',
            'token_uri': '',
            'auth_uri': ''
        }|(override or {}), f, indent=4)

def _choose_kind(default: str|None=None):
    if default is None:
        sel_kind = cast(tuple[str, int], pick.pick( # type: ignore
            ['OAuth1', 'OAuth2'],
            "Select the kind of OAuth:\n"
            "Arrows to move, Space to select, Enter to continue" ))
    else:
        assert default in ['OAuth1', 'OAuth2']
        sel_kind = (default, 0)

    match sel_kind:
        case ('OAuth1', _): return 'OAuth1'
        case ('OAuth2', _): return 'OAuth2'
        case _: sys.exit(1)

@_crtlc_exit
def scaffold_wizard(kind: str|None=None, override: JsonMap|None=None):
    app_file = _pick_app_file(False)

    if os.path.exists(app_file):
        print("Target file already exists. Overwrite? (y/n)")
        overwrite = input("> ").lower()
        if overwrite != 'y':
            sys.exit(0)

    match _choose_kind(default=kind):
        case 'OAuth1': scaffold_oauth1(app_file, override)
        case 'OAuth2': scaffold_oauth2(app_file, override)

@_crtlc_exit
async def grant_wizard(scopesType: type|None, dry_run: bool=False, kind: str|None=None):

    app_file = _pick_app_file()
    user_file = _pick_user_file()

    match _choose_kind(default=kind):
        case 'OAuth1':
            if not dry_run:
                await grant_oauth1(app_file, user_file)
            else:
                print("Dry run: skipping OAuth1 grant.")
        case 'OAuth2':
            if scopesType is None:
                print("Enter a space-separated list of scopes to authorize:")
                scopes = input("> ").split()
            else:
                scopes = pick_scopes(scopesType)
            if not scopes:
                print("No scopes selected. Exiting.")
                sys.exit(1)
            if not dry_run:
                await grant_oauth2(app_file, user_file, scopes)
            else:
                print("Dry run: skipping OAuth2 grant.")

    print(F"User credentials have been saved to {user_file}.")
