"""Setup configuration for Amazon Parental Dashboard Controller."""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

# Read requirements
requirements = (this_directory / "requirements.txt").read_text().splitlines()

setup(
    name="amazon-parental-dashboard",
    version="1.0.0",
    author="Amazon Parental Dashboard Contributors",
    description="Control and monitor Amazon Parental Dashboard through Home Assistant via MQTT",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/amazon-parental-dashboard",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Home Automation",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "amazon-parental=amazon_parental.control:main",
            "amazon-dashboard-ha=dashboard_to_homeassistant:main",
        ],
    },
    include_package_data=True,
    package_data={
        "amazon_parental": ["*.json"],
    },
)
