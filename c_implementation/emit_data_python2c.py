import os
import numpy as np
from matrix_generator_for_c import get_H_x, get_H_z, get_A_x, get_A_z

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "c_implementation", "generated")


def emit_c_matrix(f, arr, name, ctype):
    """二维 numpy array -> 扁平一维 C 数组 + 维度宏 + 访问宏。"""
    arr = np.ascontiguousarray(arr)
    rows, cols = arr.shape
    flat = arr.ravel()                    # ravel 总是 C order (row-major)
    upper = name.upper()
    f.write(f"#define {upper}_ROWS {rows}\n")
    f.write(f"#define {upper}_COLS {cols}\n")
    f.write(f"#define {upper}_AT(r, c) ({name}[(r) * {upper}_COLS + (c)])\n\n")
    f.write(f"static const {ctype} {name}[{flat.size}] = {{\n")
    for i in range(0, flat.size, 36):
        f.write("    " + ",".join(map(str, flat[i:i + 36])) + ",\n")
    f.write("};\n\n")


def main():
    Hx = get_H_x().astype(np.int64)
    Hz = get_H_z().astype(np.int64)
    Ax = get_A_x().astype(np.int64)

    assert Hx.shape == (72, 144) and Ax.shape == (12, 144)
    assert np.all(Hx.sum(axis=1) == 6), "row weight 必须是 6"
    assert np.all(Hx.sum(axis=0) == 3), "column weight 必须是 3"
    assert np.all((Hx @ Hz.T) % 2 == 0), "CSS 条件 H_x·H_z^T = 0 不成立"
    assert np.all((Ax @ Hz.T) % 2 == 0), "A_x 和 H_x 配对搞反了"

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "code_matrices.h")
    with open(path, "w") as f:
        f.write("/* 由 integrated_cnu_vnu/emit_c_data.py 生成,不要手改 */\n")
        f.write("/* gross code [[144,12,12]]: BBCode({x:12, y:6}, x^3+y+y^2, y^3+x+x^2) */\n")
        f.write("#ifndef CODE_MATRICES_H\n#define CODE_MATRICES_H\n#include <stdint.h>\n\n")
        emit_c_matrix(f, Hx.astype(np.uint8), "h_x", "uint8_t")
        emit_c_matrix(f, Ax.astype(np.uint8), "a_x", "uint8_t")
        f.write("#endif\n")
    print(f"wrote {path} ({os.path.getsize(path)} bytes)")


if __name__ == "__main__":
    main()