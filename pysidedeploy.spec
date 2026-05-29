[app]

title = AViz
project_dir = .
input_file = main.py
icon =

[python]

packages = numpy,scipy,pyqtgraph

android_packages = buildozer==1.5.0,cython==0.29.33

[qt]

modules = Core,Gui,Widgets,OpenGL,Multimedia
plugins =

[android]

plugins = platforms,platforminputcontexts,xcbglintegrations,wayland-decoration-client,wayland-graphics-integration-client,wayland-shell-integration,egldeviceintegrations,generic,iconengines,imageformats,networkinformation,platforms/darwin,platforms/directfb,tls,styles,assetimporters,sceneparsers,renderers,renderplugins,geometryloaders,sceneparsers,canbus,playlistformats,multimedia

[buildozer]

mode = debug
arch = aarch64
# Set explicitly in CI/local builds (deploy skips cache lookup when this file exists):
# ndk_path = /home/you/.pyside6_android_deploy/android-ndk/android-ndk-r27c
# sdk_path = /home/you/.pyside6_android_deploy/android-sdk
