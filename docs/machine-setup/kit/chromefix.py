import playwright.sync_api as _sa
from playwright._impl._browser_type import BrowserType as _BT
from playwright.sync_api import BrowserType
_orig = BrowserType.launch
def launch(self, *a, **k):
    if self.name == "chromium" and not k.get("executable_path"):
        k.setdefault("channel", "chrome")
    return _orig(self, *a, **k)
BrowserType.launch = launch
