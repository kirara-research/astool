#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <structmember.h>

#include <stdint.h>
#include <stdlib.h>

struct hwd_keyset {
    uint32_t k1;
    uint32_t k2;
    uint32_t k3;
};

typedef struct {
    PyObject_HEAD
    struct hwd_keyset pk;
} hwd_keyset_t;

int hwdecrypt_exec_module(PyObject *module);
static int keyset_init(hwd_keyset_t *self, PyObject *args, PyObject *kwds);
static PyObject *decrypt_buffer(PyObject *self, PyObject *const *args, Py_ssize_t nargs);

static const PyMemberDef HWDKeysetTypeMembers[] = {
    {"key1", T_UINT, offsetof(hwd_keyset_t, pk.k1), 0, "key1"},
    {"key2", T_UINT, offsetof(hwd_keyset_t, pk.k2), 0, "key2"},
    {"key3", T_UINT, offsetof(hwd_keyset_t, pk.k3), 0, "key3"},
    {NULL} /* Sentinel */
};
static const PyType_Slot HWDKeysetTypeSlots[] = {
    {Py_tp_doc, "Contains the RNG state for the stream cipher."},
    {Py_tp_new, PyType_GenericNew},
    {Py_tp_init, (initproc)keyset_init},
    {Py_tp_members, &HWDKeysetTypeMembers},
    {0, NULL}
};
static const PyType_Spec HWDKeysetType = {
    .name = "hwdecrypt.Keyset",
    .basicsize = sizeof(hwd_keyset_t),
    .itemsize = 0,
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HEAPTYPE,
    .slots = &HWDKeysetTypeSlots,
};

static const PyMethodDef HWDTopLevel[] = {
    {"decrypt", decrypt_buffer, METH_FASTCALL, "Decrypt the data within a buffer object."},
    {NULL, NULL, 0, NULL}
};

static const PyModuleDef_Slot modslots[] = {
    {Py_mod_exec, &hwdecrypt_exec_module},
    {0, NULL}
};

typedef struct {
    PyObject *keyset_type;
} hwd_module_private_t;

static PyModuleDef modinfo = {
    PyModuleDef_HEAD_INIT,
    .m_name = "hwdecrypt",
    .m_doc = "C extension module for decrypting ICE data.",
    .m_size = sizeof(hwd_module_private_t),
    .m_methods = HWDTopLevel,
    .m_slots = &modslots,
};

#define hwd_K3_DEFAULT 0x3039
void hwd_decrypt_buf(struct hwd_keyset *initp, uint8_t *buf, int size);

////////////////////////////////////////////////////////

static int keyset_init(hwd_keyset_t *self, PyObject *args, PyObject *kwds) {
    unsigned long k1l, k2l, k3l = hwd_K3_DEFAULT;

    if (!PyArg_ParseTuple(args, "kk|k", &k1l, &k2l, &k3l)) {
        return -1;
    }

    self->pk.k1 = (uint32_t)k1l;
    self->pk.k2 = (uint32_t)k2l;
    self->pk.k3 = (uint32_t)k3l;

    return 0;
}

static PyObject *decrypt_buffer(PyObject *self, PyObject *const *args, Py_ssize_t nargs) {
    hwd_module_private_t *private = PyModule_GetState(self);
    hwd_keyset_t *keyset;
    Py_buffer edata;

    if (nargs != 2) {
        PyErr_SetString(PyExc_TypeError, "Wrong number of arguments.");
        return NULL;
    }

    if (Py_TYPE(args[0]) != private->keyset_type) {
        PyErr_SetString(PyExc_TypeError, "The first argument must be a Keyset.");
        return NULL;
    }
    keyset = (hwd_keyset_t *)args[0];

    if (PyObject_GetBuffer(args[1], &edata, PyBUF_WRITABLE | PyBUF_SIMPLE) != 0) {
        return NULL;
    }

    if (edata.len > INT_MAX || edata.len < 0) {
        PyErr_SetString(PyExc_ValueError, "invalid size");
        PyBuffer_Release(&edata);
        return NULL;
    }

    hwd_decrypt_buf(&keyset->pk, edata.buf, edata.len);
    PyBuffer_Release(&edata);

    Py_RETURN_NONE;
}

int hwdecrypt_exec_module(PyObject *module) {
    PyObject *kstype_real = PyType_FromSpec(&HWDKeysetType);
    if (PyModule_AddObject(module, "Keyset", (PyObject *)kstype_real) < 0) {
        Py_DECREF(kstype_real);
        return -1;
    }

    hwd_module_private_t *private = PyModule_GetState(module);
    private->keyset_type = kstype_real;
    return 0;
}

PyMODINIT_FUNC PyInit_hwdecrypt(void) {
    PyObject *m = PyModuleDef_Init(&modinfo);
    if (m == NULL) {
        return NULL;
    }

    return m;
}