import sys
from setuptools import setup, Extension


def main():
    args = dict(
        name="astool",
        version="1.0.0",
        description="Tooling for interacting with remote and local AS resources.",
        packages=["astool", "astool_extra"],
        ext_modules=[],
        package_data={"astool": ["ex_bootstrap_script/*.json"]},
        install_requires=["cryptography<3.0", "requests<3.0.0", "plac<2.0.0"],
        extras_require={"async_pkg": ["aiohttp<3.7.0"]}
    )

    if "--without-hwdecrypt" not in sys.argv:
        args["ext_modules"].append(
            Extension(
                "hwdecrypt",
                sources=["hwdecrypt_src/hwdecrypt_module.c", "hwdecrypt_src/hwd_tool.c"],
                py_limited_api=True,
            )
        )
    else:
        sys.argv[:] = [x for x in sys.argv if x != "--without-hwdecrypt"]

    setup(**args)


if __name__ == "__main__":
    main()
