def main():
    g = Glasses()
    for glass in g.glasses:
        print(glass.v)

    print(g.closest_glass(n=1.8, v=40))

    # wavelength = 365
    # coefficients = [
    #     3.1860388,
    #     -0.013756822,
    #     0.029614017,
    #     0.0012383727,
    #     -8.0134175e-05,
    #     7.2330635e-06
    #     ]
    # print(sellmeier(coefficients, wavelength))


if __name__ == '__main__':
    main()
