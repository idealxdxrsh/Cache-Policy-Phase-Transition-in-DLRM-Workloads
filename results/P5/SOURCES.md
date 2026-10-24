# P5 sources and build record (2026-10-24, local machine, Ubuntu 24.04.4, gcc 13.3.0)

## NanGate45 liberty (NOT committed; `.gitignore`: `NangateOpenCellLibrary*.lib`)
- URL: https://raw.githubusercontent.com/The-OpenROAD-Project/OpenROAD-flow-scripts/6c6fc7e21b2d0b5b88b1a52d0a5860ea4d88e9e5/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib
- OpenROAD-flow-scripts commit 6c6fc7e21b2d0b5b88b1a52d0a5860ea4d88e9e5 (2021-07-20, last commit touching this file)
- Local path: `~/eda/pdk/nangate45/NangateOpenCellLibrary_typical.lib`
- Size 6,692,032 bytes; sha256 8d540a4d4cf6d09d27c87ad067857a9c0c2eeb023ab7a56e058cd3113db4e9b1
- Corner (file header): typical, TypTyp, 25C, 1.1V; characterised with NGLibraryCharacterizer v2011.01.
- Licence: `flow/platforms/nangate45/LICENSE` in that repo is Apache-2.0. The liberty file's own header says instead:
  "Copyright (C) 2004-2011, Nangate Inc. All rights reserved." ... "This file has been provided pursuant to a License
  Agreement containing restrictions on its use. This file contains valuable trade secrets and proprietary information
  of Nangate Inc., and is protected by U.S. and international laws and/or treaties." The agreement itself is not in the
  file. The file is used locally only and not redistributed.

## CUDD (BSD-3-Clause)
- https://github.com/cuddorg/cudd.git, tag 3.0.0 = commit f54f533303640afd5dbe47a05ebeabb3066f2a25; source `~/eda/src/cudd`
- Build (the touch avoids an automake re-run caused by git checkout timestamps):
  `touch aclocal.m4; sleep 1; touch configure Makefile.in config.h.in; ./configure --prefix=$HOME/eda; make -j8; make install`
- Installed: `~/eda/lib/libcudd.a`, `~/eda/include/cudd.h`

## OpenSTA (GPL-3.0)
- https://github.com/parallaxsw/OpenSTA.git, commit 7b261909c1730d963252142e136daaa0199e333c (2026-10-09, newest master
  commit at least 2 weeks old); source `~/eda/src/OpenSTA`
- Build: `mkdir build; cd build; cmake -DCUDD_DIR=$HOME/eda -DCMAKE_INSTALL_PREFIX=$HOME/eda ..; make -j8; make install`
- `~/eda/bin/sta -version`: 3.1.0; banner "OpenSTA 3.1.0 7b261909c1"

## System packages (user ran `sudo apt install cmake swig bison flex tcl-dev libeigen3-dev`)
- cmake 3.28.3-1build7, swig 4.2.0-2ubuntu1, bison 2:3.8.2+dfsg-1ubuntu0.24.04.1, flex 2.6.4-8.2build1,
  tcl-dev 8.6.14build1, libeigen3-dev 3.4.0-4build0.1 (`dpkg -l`)

## Already present
- Yosys 0.33 (git sha1 2584903a060), Icarus Verilog (`/usr/bin/iverilog`)

## OpenSTA check on a hand-checkable netlist (`synthesis/p5/sta_check/`, output `sta_check_inv1.txt`)
- One INV_X1, input slew 0.00117378 ns and load 3.795620 fF (both liberty table index points, no interpolation).
- Liberty tables: cell_rise 0.0142069, cell_fall 0.00763425, rise_transition 0.0110850, fall_transition 0.00507790 ns.
- OpenSTA: rise delay 0.0142069, fall delay 0.0076343, slews 0.0110850 / 0.0050779 ns, slack 0.9857931 ns at 1.0 ns
  (= 1 - 0.0142069). These match.
