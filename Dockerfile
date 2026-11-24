FROM ubuntu:24.04 AS build

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git ca-certificates \
        libboost-all-dev libgmp-dev libmpfr-dev \
    && rm -rf /var/lib/apt/lists/*

# CGAL is header-only, so installing just copies headers and cmake files
ARG CGAL_VERSION=v6.0.1
RUN git clone --depth 1 --branch ${CGAL_VERSION} https://github.com/CGAL/cgal.git /tmp/cgal \
    && cmake -S /tmp/cgal -B /tmp/cgal/build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /tmp/cgal/build --target install \
    && rm -rf /tmp/cgal

WORKDIR /app
COPY CMakeLists.txt main.cpp ./

# Fully static build: point CGAL at the static GMP/MPFR archives
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DWRAP_STATIC=ON \
        -DGMP_LIBRARY_RELEASE="$(find /usr/lib -name libgmp.a | head -1)" \
        -DGMP_LIBRARY_DEBUG="$(find /usr/lib -name libgmp.a | head -1)" \
        -DGMPXX_LIBRARIES="$(find /usr/lib -name libgmpxx.a | head -1)" \
        -DMPFR_LIBRARIES="$(find /usr/lib -name libmpfr.a | head -1)" \
    && cmake --build build -j"$(nproc)" \
    && (ldd build/wrap 2>&1 | grep -q "not a dynamic executable")


# Optional: `docker build --target export --output type=local,dest=./bin .`
# writes the static binary to ./bin/wrap. Keep this stage before the final one
# so a plain `docker build` still produces the runtime image.
FROM scratch AS export
COPY --from=build /app/build/wrap /wrap


FROM scratch

COPY --from=build /app/build/wrap /wrap

WORKDIR /data
ENTRYPOINT ["/wrap"]
