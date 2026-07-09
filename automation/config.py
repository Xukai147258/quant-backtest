# automation/config.py
import os

class Config:
    def __init__(self):
        self.api_key = os.getenv("GLM_API_KEY", "")
        self.api_base = os.getenv("GLM_API_BASE", "https://yuanyuaicloud.cn/v1")
        self.model = os.getenv("GLM_MODEL", "glm-5.2")

    @classmethod
    def from_env(cls):
        return cls()

    def validate(self):
        if not self.api_key:
            raise ValueError("GLM_API_KEY not set")
