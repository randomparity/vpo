# ============================================================================
# Stage 1: build toolchains, external libs, and FFmpeg from source
# ============================================================================
FROM ubuntu:24.04 AS builder
ARG DEBIAN_FRONTEND=noninteractive
ARG FFMPEG_BRANCH=master
ARG MAKE_JOBS=8

RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
 && add-apt-repository -y universe \
 && apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates wget curl git tar xz-utils unzip pkg-config \
    build-essential autoconf automake libtool cmake meson ninja-build \
    yasm nasm \
    python3 python3-pip python3-setuptools \
    # image/font/subtitle/filter stacks
    libass-dev libfreetype6-dev libfribidi-dev libfontconfig1-dev libxml2-dev \
    libopenjp2-7-dev libwebp-dev libtiff-dev libpng-dev libjpeg-dev \
    # libplacebo built from source below for FFmpeg 8 compatibility
    # audio codecs
    libmp3lame-dev libopus-dev libvorbis-dev libsoxr-dev libspeex-dev \
    # video codecs & accel
    libx264-dev libx265-dev libnuma-dev \
    libvpx-dev libaom-dev libsvtav1enc-dev libdav1d-dev \
    libdrm-dev libva-dev libvdpau-dev \
    # containers, nets, crypto
    libbluray-dev libzmq3-dev librtmp-dev libssh-dev \
    libsrt-openssl-dev librist-dev libssl-dev \
    # analysis / quality
    # (no libvmaf-dev here — we build libvmaf from source)
    # misc
    libvidstab-dev libchromaprint-dev frei0r-plugins-dev \
    libtheora-dev libxvidcore-dev \
    zlib1g-dev libbz2-dev liblzma-dev libzstd-dev \
    libasound2t64 libpulse-dev libjack-jackd2-dev \
    libv4l-dev \
    libzimg-dev \
    libsdl2-dev \
    libvulkan-dev \
    glslang-dev \
    libepoxy-dev \
    liblcms2-dev \
    libxxhash-dev \
 && rm -rf /var/lib/apt/lists/*

ENV PREFIX=/usr/local
ENV PATH=${PREFIX}/bin:$PATH
WORKDIR /tmp/src

# --- Build fdk-aac (nonfree) ---
RUN git clone --depth=1 https://github.com/mstorsjo/fdk-aac.git \
 && cd fdk-aac && autoreconf -fiv \
 && ./configure --prefix="${PREFIX}" --enable-shared \
 && make -j"${MAKE_JOBS}" && make install && ldconfig

# --- NVENC headers ---
RUN git clone --depth=1 https://github.com/FFmpeg/nv-codec-headers.git \
 && cd nv-codec-headers && make PREFIX="${PREFIX}" && make install PREFIX="${PREFIX}"

# --- Build libvmaf from source (models included) ---
# Official repo & build system: meson/ninja
RUN git clone --depth=1 https://github.com/Netflix/vmaf.git \
 && cd vmaf/libvmaf \
 && meson setup build --prefix="${PREFIX}" --buildtype=release \
 && ninja -C build && ninja -C build install && ldconfig \
 && mkdir -p /usr/local/share/model && cp -a /tmp/src/vmaf/model/* /usr/local/share/model/

# --- Build libplacebo from source (FFmpeg 8 requires newer API than Ubuntu 24.04 provides) ---
RUN git clone --depth=1 --recursive https://code.videolan.org/videolan/libplacebo.git \
 && cd libplacebo \
 && meson setup build --prefix="${PREFIX}" --buildtype=release \
    -Dvulkan=enabled -Dshaderc=disabled -Dglslang=enabled -Ddemos=false -Dtests=false \
 && ninja -C build && ninja -C build install && ldconfig

# --- FFmpeg from source ---
RUN git clone --depth=1 -b "${FFMPEG_BRANCH}" https://github.com/FFmpeg/FFmpeg.git ffmpeg
WORKDIR /tmp/src/ffmpeg

# Look for models in both distro and /usr/local
ENV VMAF_MODEL_PATH=/usr/local/share/model:/usr/share/model

# Compute multiarch triplet and ensure pkg-config/ld paths for configure
RUN export DEB_HOST_MULTIARCH=$(dpkg-architecture -q DEB_HOST_MULTIARCH) \
  && export PKG_CONFIG_PATH="${PREFIX}/lib/pkgconfig:${PREFIX}/lib/${DEB_HOST_MULTIARCH}/pkgconfig:/usr/lib/${DEB_HOST_MULTIARCH}/pkgconfig:${PKG_CONFIG_PATH}" \
  && export LD_LIBRARY_PATH="${PREFIX}/lib:${PREFIX}/lib/${DEB_HOST_MULTIARCH}:${LD_LIBRARY_PATH}" \
  && ./configure \
  --prefix="${PREFIX}" \
  --extra-cflags="-I${PREFIX}/include" \
  --extra-ldflags="-L${PREFIX}/lib" \
  --extra-libs="-lpthread -lm" \
  --enable-gpl --enable-nonfree \
  \
  --enable-libx264 --enable-libx265 --enable-libvpx \
  --enable-libaom --enable-libsvtav1 --enable-libdav1d \
  --enable-libmp3lame --enable-libvorbis --enable-libopus \
  --enable-libfdk-aac \
  \
  --enable-libass --enable-libfreetype --enable-libfribidi \
  --enable-libopenjpeg --enable-libwebp --enable-libvmaf \
  --enable-libvidstab --enable-libplacebo --enable-frei0r \
  --enable-chromaprint \
  \
  --enable-openssl \
  --enable-libsrt --enable-librist --enable-librtmp --enable-libzmq --enable-libssh \
  \
  --enable-vaapi --enable-vdpau --enable-libdrm --enable-v4l2-m2m \
  --enable-nvenc \
  \
  --enable-libsoxr --enable-zlib --enable-bzlib --enable-lzma --enable-libzimg \
  --enable-libtheora --enable-libxvid \
  \
  --enable-ffmpeg --disable-ffplay --enable-ffprobe

RUN make -j"${MAKE_JOBS}" && make install && ldconfig

# ============================================================================
# Stage 2: runtime
# ============================================================================
FROM ubuntu:24.04 AS runtime
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
 && add-apt-repository -y universe \
 && apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    # runtime deps matching what we linked
    libass9 libfreetype6 libfribidi0 libfontconfig1 libxml2 \
    libopenjp2-7 libwebp7 libtiff6 libpng16-16 libjpeg-turbo8 \
    libwebpmux3 libwebpdemux2 \
    # libplacebo provided via /usr/local from builder stage
    libmp3lame0 libopus0 libvorbis0a libvorbisenc2 libsoxr0 libspeex1 \
    libx264-164 libx265-199 libnuma1 \
    libvpx9 libaom3 libsvtav1enc1d1 libdav1d7 \
    libdrm2 libva2 libva-drm2 libva-x11-2 libva-wayland2 libvdpau1 \
    libbluray2 libzmq5 librtmp1 libssh-4 \
    libsrt1.5-openssl librist4 libssl3 \
    # libvmaf comes from /usr/local (built earlier)
    libvidstab1.1 libchromaprint1 frei0r-plugins \
    libtheora0 libxvidcore4 \
    libzimg2 \
    libsdl2-2.0-0 \
    libsndio7.0 \
    libxv1 libx11-6 libxext6 \
    zlib1g libbz2-1.0 liblzma5 libzstd1 \
    libasound2t64 libpulse0 libjack-jackd2-0 \
    libv4l-0 \
    libvulkan1 \
    libepoxy0 \
    liblcms2-2 \
    libxxhash0 \
 && rm -rf /var/lib/apt/lists/*

ENV VMAF_MODEL_PATH=/usr/local/share/model:/usr/share/model
COPY --from=builder /usr/local /usr/local
ENV PATH=/usr/local/bin:$PATH
# Ensure dynamic linker can find libraries installed under /usr/local for all arches
RUN export DEB_HOST_MULTIARCH=$(dpkg-architecture -q DEB_HOST_MULTIARCH) \
 && printf "/usr/local/lib\n/usr/local/lib/%s\n" "$DEB_HOST_MULTIARCH" > /etc/ld.so.conf.d/ffmpeg-local.conf \
 && ldconfig
CMD ["ffmpeg", "-hide_banner", "-version"]
