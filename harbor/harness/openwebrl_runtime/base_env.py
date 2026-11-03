"""Small dependency-free base class used by the vendored OpenWebRL WebEnv.

The upstream class imports timeout_decorator only to decorate an abstract method. The WebHarbor image does not need that package because the concrete async WebEnv methods and the outer rollout timeout provide the actual runtime limits.
"""

from abc import ABC, abstractmethod


class BaseEnv(ABC):
    def __init__(self, server_path, platform, **kwargs):
        self.server_path = server_path
        self.platform = platform
        self.action_history = []

    @abstractmethod
    def reset(self, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def get_screen_size(self) -> tuple[int, int]:
        raise NotImplementedError

    def onScreen(self, x, y):
        screen_width, screen_height = self.get_screen_size()
        if isinstance(x, float) and isinstance(y, float):
            assert 0 <= x <= 1 and 0 <= y <= 1
            x = round(x * screen_width)
            y = round(y * screen_height)
        return 0 <= x < screen_width and 0 <= y < screen_height

    @abstractmethod
    def get_screenshot(self):
        raise NotImplementedError

    @abstractmethod
    def get_a11ytree(self):
        raise NotImplementedError

    @abstractmethod
    def start_recording(self):
        raise NotImplementedError

    @abstractmethod
    def end_recording(self):
        raise NotImplementedError

    def get_obs(self, return_screenshot=True, return_a11ytree=False):
        assert return_screenshot or return_a11ytree
        result = {}
        if return_screenshot:
            result["screenshot"] = self.get_screenshot()
        if return_a11ytree:
            result["a11ytree"] = self.get_a11ytree()
        return result

    @abstractmethod
    def execute_single_action(self, action: dict):
        raise NotImplementedError

    def execute(self, action_list: list[dict]):
        for action in action_list:
            self.execute_single_action(action)

    def parse_action(self, prediction):
        return None
