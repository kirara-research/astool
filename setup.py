import sys
from setuptools import setup, Extension


def main():
    args = dict(
        name="astool",
        version="1.0.0",
        description="Tooling for interacting with remote and local AS resources.",
        packages=["astool"],
        ext_modules=[],
        package_data={"astool": ["ex_bootstrap_script/*.json"]},
    )

    if "--without-hwdecrypt" not in sys.argv:
        args["ext_modules"].append(
            Extension(
                "hwdecrypt",
                sources=["hwdecrypt_src/hwdecrypt_module.c", "hwdecrypt_src/hwd_tool.c"],
                py_limited_api=True,
            )
        )

    setup(**args)


if __name__ == "__main__":
    main()
