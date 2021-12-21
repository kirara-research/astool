from setuptools import setup, Extension

setup(
    ext_modules=[
        Extension(
            "hwdecrypt", sources=["hwdecrypt_module.c", "hwd_tool.c"], py_limited_api=True
        )
    ],
)
