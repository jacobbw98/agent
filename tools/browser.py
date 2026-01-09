"""
Browser Tool - Playwright-based browser automation.
"""
import asyncio
from playwright.async_api import async_playwright, Browser, Page
from typing import Optional
import base64


class BrowserTool:
    """Browser automation tool using Playwright."""
    
    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._loop = None
    
    def _get_loop(self):
        """Get or create event loop."""
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop
    
    async def _ensure_browser(self):
        """Ensure browser is started."""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=False)
            self._page = await self._browser.new_page()
    
    async def _navigate(self, url: str) -> str:
        """Navigate to a URL."""
        await self._ensure_browser()
        await self._page.goto(url, wait_until="domcontentloaded")
        return f"Navigated to {url}. Title: {await self._page.title()}"
    
    async def _click(self, selector: str = None, x: int = None, y: int = None) -> str:
        """Click an element by selector or coordinates."""
        await self._ensure_browser()
        if selector:
            await self._page.click(selector)
            return f"Clicked element: {selector}"
        elif x is not None and y is not None:
            await self._page.mouse.click(x, y)
            return f"Clicked at coordinates ({x}, {y})"
        return "Error: Must provide selector or x,y coordinates"
    
    async def _type(self, text: str, selector: str = None) -> str:
        """Type text, optionally into a specific element."""
        await self._ensure_browser()
        if selector:
            await self._page.fill(selector, text)
            return f"Typed into {selector}"
        else:
            await self._page.keyboard.type(text)
            return f"Typed: {text[:50]}..."
    
    async def _press_key(self, key: str) -> str:
        """Press a keyboard key."""
        await self._ensure_browser()
        await self._page.keyboard.press(key)
        return f"Pressed key: {key}"
    
    async def _screenshot(self) -> str:
        """Take a screenshot and return as base64."""
        await self._ensure_browser()
        screenshot = await self._page.screenshot()
        b64 = base64.b64encode(screenshot).decode()
        return f"Screenshot captured ({len(screenshot)} bytes)"
    
    async def _get_content(self) -> str:
        """Get page text content."""
        await self._ensure_browser()
        content = await self._page.inner_text("body")
        # Truncate if too long
        if len(content) > 5000:
            content = content[:5000] + "\n... (truncated)"
        return content
    
    async def _get_url(self) -> str:
        """Get current page URL."""
        await self._ensure_browser()
        return self._page.url
    
    async def _close(self):
        """Close browser."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
    
    # Sync wrappers
    def navigate(self, url: str) -> str:
        return asyncio.get_event_loop().run_until_complete(self._navigate(url))
    
    def click(self, selector: str = None, x: int = None, y: int = None) -> str:
        return asyncio.get_event_loop().run_until_complete(self._click(selector, x, y))
    
    def type_text(self, text: str, selector: str = None) -> str:
        return asyncio.get_event_loop().run_until_complete(self._type(text, selector))
    
    def press_key(self, key: str) -> str:
        return asyncio.get_event_loop().run_until_complete(self._press_key(key))
    
    def screenshot(self) -> str:
        return asyncio.get_event_loop().run_until_complete(self._screenshot())
    
    def get_content(self) -> str:
        return asyncio.get_event_loop().run_until_complete(self._get_content())
    
    def get_url(self) -> str:
        return asyncio.get_event_loop().run_until_complete(self._get_url())
    
    def close(self):
        return asyncio.get_event_loop().run_until_complete(self._close())


# Singleton instance
_browser_tool: Optional[BrowserTool] = None


def get_browser() -> BrowserTool:
    """Get or create browser tool instance."""
    global _browser_tool
    if _browser_tool is None:
        _browser_tool = BrowserTool()
    return _browser_tool
