# Sample Geospatial Datasets for Local Testing

This directory provides small, valid, and self-contained sample datasets for testing the **Geospatial File Measurement API**.

Both datasets contain identical known geometries in Bangalore, India (~13° N, 77.6° E) in **WGS 84 (EPSG:4326)** coordinates to verify multi-format ingestion and dynamic UTM metric projection.

---

## 📦 Included Sample Files

| File | Format | Size | Description |
| :--- | :--- | :--- | :--- |
| [`sample_data.kml`](file:///c:/Users/ramachandra/microsoft%20project/geospatial_file_mangage_01/samples/sample_data.kml) | Google Earth KML 2.2 | ~1.4 KB | Clean XML containing Polygon, LineString, and Point placemarks |
| [`sample_shapefile.zip`](file:///c:/Users/ramachandra/microsoft%20project/geospatial_file_mangage_01/samples/sample_shapefile.zip) | Zipped ESRI Shapefile | ~2.7 KB | Multi-layer archive containing `.shp`, `.shx`, `.dbf`, and `.prj` |

---

## 🗺️ Known Geometries & Expected Measurements

Both files contain three distinct features:

1. **Polygon: `Central Park Lake Reserve` (`poly_001`)**
   - **Coordinates**: Box bounded by `(77.5900, 12.9700)` to `(77.5950, 12.9750)` (~$550\text{ m} \times 550\text{ m}$)
   - **Source CRS**: `EPSG:4326` (WGS 84 in degrees)
   - **Measurement CRS**: `EPSG:32643 (UTM Zone 43N)`
   - **Expected Area**: $\approx 300,422.8\text{ m}^2$ ($\approx 0.3004\text{ km}^2$)
   - **Measurement Status**: `success`

2. **LineString: `Metro Rail Transit Corridor` (`line_001`)**
   - **Coordinates**: Linear transect from `(77.6000, 12.9750)` through `(77.6050, 12.9780)` to `(77.6100, 12.9800)`
   - **Source CRS**: `EPSG:4326` (WGS 84 in degrees)
   - **Measurement CRS**: `EPSG:32643 (UTM Zone 43N)`
   - **Expected Length**: $\approx 1,222.5\text{ m}$ ($\approx 1.2225\text{ km}$)
   - **Measurement Status**: `success`

3. **Point: `Observation Tower Landmark` (`point_001`)**
   - **Coordinates**: Location at `(77.5925, 12.9725)`
   - **Measurement Status**: `skipped`
   - **Measurements**: `area_sq_m: null`, `length_m: null`
   - **Warning**: `"Point geometry does not require area or length measurement."`

---

## 🚀 How to Test Locally

Ensure the API server is running:
```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 1: Interactive Swagger UI (Recommended)
1. Open your browser to **[http://localhost:8000/docs](http://localhost:8000/docs)**.
2. Expand the `POST /api/files/` endpoint.
3. Click **Try it out**, click **Choose File**, select either `samples/sample_data.kml` or `samples/sample_shapefile.zip`, and click **Execute**.
4. Copy the returned `id` (e.g., `8ea6c1db-03b3-4e43-9d89-0add39e39b9c`).
5. Scroll down to `GET /api/files/{file_id}/measurements/`, enter the ID, and click **Execute** to view all calculated metrics and GeoJSON geometries.

---

### Option 2: Using `curl` (Bash / PowerShell / Terminal)

#### Upload KML:
```bash
curl -X POST "http://localhost:8000/api/files/" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@samples/sample_data.kml"
```

#### Upload Zipped Shapefile:
```bash
curl -X POST "http://localhost:8000/api/files/" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@samples/sample_shapefile.zip"
```

#### Query Measurements (replace `<FILE_ID>`):
```bash
curl -X GET "http://localhost:8000/api/files/<FILE_ID>/measurements/"
```

---

### Option 3: Using PowerShell (`Invoke-RestMethod`)

```powershell
# Upload KML sample
$form = @{ file = Get-Item "samples\sample_data.kml" }
$response = Invoke-RestMethod -Uri "http://localhost:8000/api/files/" -Method Post -Form $form
$fileId = $response.file.id
Write-Host "Uploaded KML file ID: $fileId"

# Fetch measurements
$measurements = Invoke-RestMethod -Uri "http://localhost:8000/api/files/$fileId/measurements/"
$measurements.features | Format-Table geometry_type, measurement_status, measurements
```

---

### Option 4: Using Python (`httpx` or `requests`)

```python
import httpx

client = httpx.Client(base_url="http://localhost:8000")

# Upload sample Shapefile zip
with open("samples/sample_shapefile.zip", "rb") as f:
    upload_res = client.post("/api/files/", files={"file": ("sample_shapefile.zip", f, "application/zip")})

file_id = upload_res.json()["file"]["id"]
print(f"Uploaded File ID: {file_id}")

# Fetch measurements
meas_res = client.get(f"/api/files/{file_id}/measurements/")
for feat in meas_res.json()["features"]:
    print(f"Feature: {feat['geometry_type']} | Status: {feat['measurement_status']} | Measurements: {feat['measurements']}")
```
