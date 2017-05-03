Frequently asked questions
===


I select an object and launch the script. A warning with stacktrace showing:

`AttributeError: 'NoneType' object has no attribute 'select'`
---

This indicates that there still is some selected object that is incompatible. Make sure there are no hidden object or objects on other layers that are still selected.

This actually is very important to get the desired result. The script can not know which of the selected objects are the ones that you intended to actually be selected.

