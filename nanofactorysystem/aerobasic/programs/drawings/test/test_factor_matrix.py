import numpy as np


def create_direction_grid(n_x, n_y):
    # x values: +1 at the start, -1 at the end, 0 in between
    x_vals = np.zeros(n_x)
    x_vals[0] = 1
    x_vals[-1] = -1

    # y values: +1 at the top, -1 at the bottom, 0 in between
    y_vals = np.zeros(n_y)
    y_vals[0] = 1
    y_vals[-1] = -1

    # Broadcasting: x over all rows, y over all columns
    x_grid = np.broadcast_to(x_vals, (n_y, n_x))
    y_grid = np.broadcast_to(y_vals[:, np.newaxis], (n_y, n_x))

    return np.stack([x_grid, y_grid], axis=-1)


# Test
grid = create_direction_grid(3, 3)
print("3x3:")
print(grid)

print("\n2x2:")
print(create_direction_grid(9, 9))

print("\n4x3:")
print(create_direction_grid(4, 3))