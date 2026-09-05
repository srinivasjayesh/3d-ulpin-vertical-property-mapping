import rasterio

raster_path = "data/tile_0PX-jEEaiBo.tif"

with rasterio.open(raster_path) as src:

    print("\n=== GOOGLE OPEN BUILDINGS RASTER ===")

    print("CRS:", src.crs)
    print("Width:", src.width)
    print("Height:", src.height)
    print("Number of bands:", src.count)

    print("\nBounds:")
    print(src.bounds)

    print("\nData types:")
    print(src.dtypes)

    print("\nNoData values:")
    print(src.nodatavals)

    print("\nBand descriptions:")
    for i in range(1, src.count + 1):
        print(f"Band {i}: {src.descriptions[i - 1]}")

    print("\nRaster tags:")
    print(src.tags())