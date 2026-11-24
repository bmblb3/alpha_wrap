cmake_minimum_required(VERSION 3.15)
project(wrap_demo LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

find_package(CGAL REQUIRED)

add_executable(wrap main.cpp)
target_link_libraries(wrap PRIVATE CGAL::CGAL)

option(WRAP_STATIC "Link a fully static executable (no TBB)" OFF)

if(WRAP_STATIC)
  # TBB has no static libs in most distros, so parallelism is dropped.
  # For GMP/MPFR pass the .a files: -DGMP_LIBRARIES=.../libgmp.a -DMPFR_LIBRARIES=.../libmpfr.a
  target_link_options(wrap PRIVATE -static)
else()
  # Optional parallelism
  find_package(TBB QUIET)
  if(TBB_FOUND)
    target_link_libraries(wrap PRIVATE TBB::tbb)
    target_compile_definitions(wrap PRIVATE CGAL_LINKED_WITH_TBB)
  endif()
endif()
