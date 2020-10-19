cmake_minimum_required( VERSION 3.10 )

project( siteinfo-installer )

set( PATH_PREFIX "${CMAKE_CURRENT_LIST_DIR}/.." )

set( CPACK_COMPONENTS_ALL_IN_ONE_PACKAGE on )
set( CPACK_DEBIAN_PACKAGE_SECTION        "python" )
set( CPACK_DEBIAN_PACKAGE_ARCHITECTURE   "all" )
set( CPACK_GENERATOR                     "DEB" )

set( CPACK_PACKAGE_DESCRIPTION_SUMMARY   "Siteinfo service reads information from web pages and stores it to database." )
set( CPACK_PACKAGE_NAME                  "siteinfo" )
set( CPACK_PACKAGING_INSTALL_PREFIX      "/opt/${CPACK_PACKAGE_NAME}" )
set( CPACK_DEBIAN_PACKAGE_DEPENDS "systemd,python3.6,python3-pip,python3-venv")
set( CPACK_DEBIAN_PACKAGE_SHLIBDEPS      on )
set( SERVICE_IN_FILE "${CMAKE_CURRENT_LIST_DIR}/${CPACK_PACKAGE_NAME}.service.in")
set( SERVICE_FILE "${CMAKE_CURRENT_BINARY_DIR}/${CPACK_PACKAGE_NAME}.service")
set( SERVICE_NAME "${CPACK_PACKAGE_NAME}")

configure_file( ${SERVICE_IN_FILE} ${SERVICE_FILE} )
list( APPEND CPACK_DEBIAN_PACKAGE_CONTROL_EXTRA "${CMAKE_CURRENT_BINARY_DIR}/postinst;\
${CMAKE_CURRENT_BINARY_DIR}/prerm;${CMAKE_CURRENT_BINARY_DIR}/postrm;" )

file( STRINGS version.info MajorVersion REGEX "MajorVersion" )
file( STRINGS version.info MinorVersion REGEX "MinorVersion" )
file( STRINGS version.info PatchVersion REGEX "PatchVersion" )
file( STRINGS version.info Contact REGEX "Contact" )
file( STRINGS version.info LegalCopyright REGEX "LegalCopyright" )

set_property( DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS version.info )

string( REGEX REPLACE "[ \t]*MajorVersion[ \t]*=[ \t]*([0-9]+)" "\\1" CPACK_PACKAGE_VERSION_MAJOR "${MajorVersion}" )
string( REGEX REPLACE "[ \t]*MinorVersion[ \t]*=[ \t]*([0-9]+)" "\\1" CPACK_PACKAGE_VERSION_MINOR "${MinorVersion}" )
string( REGEX REPLACE "[ \t]*PatchVersion[ \t]*=[ \t]*([0-9]+)" "\\1" CPACK_PACKAGE_VERSION_PATCH "${PatchVersion}" )
string( REGEX REPLACE "[ \t]*Contact[ \t]*=[ \t\"]*(([^ \"]+)|())[ \"\t]*" "\\1" CPACK_PACKAGE_CONTACT "${Contact}" )
string( REGEX REPLACE "[ \t]*LegalCopyright[ \t]*=[ \t\"]*(([^\"]+)|())[ \"\t]*" "\\1" CPACK_PACKAGE_VENDOR  "${LegalCopyright}" )

install( DIRECTORY "${PATH_PREFIX}/app"
DESTINATION ./ COMPONENT ${PROJECT_NAME}
FILES_MATCHING PATTERN *.py PATTERN *.txt )

install( DIRECTORY "${PATH_PREFIX}/config"
DESTINATION ./ COMPONENT ${PROJECT_NAME}
FILES_MATCHING PATTERN *.json )

install( FILES version.info DESTINATION . COMPONENT ${PROJECT_NAME} )
install( FILES ${PATH_PREFIX}/run.py DESTINATION . COMPONENT ${PROJECT_NAME} )
install( FILES ${PATH_PREFIX}/README.md DESTINATION . COMPONENT ${PROJECT_NAME} )
install( FILES ${CMAKE_CURRENT_BINARY_DIR}/${CPACK_PACKAGE_NAME}.service
DESTINATION /etc/systemd/system/ COMPONENT ${PROJECT_NAME})

set( POSTINST "${CMAKE_CURRENT_BINARY_DIR}/postinst")
file( WRITE ${POSTINST}
"#!/bin/sh

case \"$1\" in
    configure)
    /usr/bin/python3 -m venv \"${CPACK_PACKAGING_INSTALL_PREFIX}/env\"
    sudo -H ${CPACK_PACKAGING_INSTALL_PREFIX}/env/bin/python -m pip install -U 'pip>=20.2'
    sudo -H ${CPACK_PACKAGING_INSTALL_PREFIX}/env/bin/python -m pip install --use-feature=2020-resolver -r \"${CPACK_PACKAGING_INSTALL_PREFIX}/app/requirements.txt\"
    systemctl daemon-reload
    systemctl enable ${SERVICE_NAME}
    systemctl start ${SERVICE_NAME}
;;
esac

exit 0
")

set( PRERM "${CMAKE_CURRENT_BINARY_DIR}/prerm" )
file( WRITE ${PRERM}
"#!/bin/sh

[ \"$1\" = \"remove\" ] && (
    systemctl stop ${SERVICE_NAME}
    systemctl disable ${SERVICE_NAME}
    rm -rf \"${CPACK_PACKAGING_INSTALL_PREFIX}/env\"
    find \"${CPACK_PACKAGING_INSTALL_PREFIX}/app\" -name "__pycache__" -type d -print0 | xargs -0 rm -rf
    )

exit 0
")

set( POSTRM "${CMAKE_CURRENT_BINARY_DIR}/postrm")
file( WRITE ${POSTRM}
"#!/bin/sh

[ \"$1\" = \"purge\" ] && rm \"${CPACK_PACKAGING_INSTALL_PREFIX}/requests_and_data.db\"

exit 0
")

include( CPack )
