import sys
from setuptools import setup, Extension


def main():
    args = dict(
        name="astool",
        version="1.1.0.7",
        description="Tooling for interacting with remote and local AS resources.",
        packages=["astool", "astool_extra"],
        ext_modules=[],
        package_data={"astool": ["ex_bootstrap_script/*.json"]},
        install_requires=["cryptography<4.0.0", "requests<3.0.0", "plac<2.0.0"],
        extras_require={"async_pkg": ["aiohttp<4.0.0"]}
    )

    setup(**args)


if __name__ == "__main__":
    main()
