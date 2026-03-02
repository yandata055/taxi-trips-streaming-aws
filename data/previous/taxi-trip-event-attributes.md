---
noteId: "5fece0e0135a11f1a81c43afb284b0e9"
tags: []

---

### Taxi Trip Event Attributes

The following table summarizes the attributes of both **start‑trip** and **end‑trip** event records.

| **Start‑Trip Attribute**       | **Description**                  | **End‑Trip Attribute**       | **Description**                  |
|--------------------------------|------------------------------------------------|------------------------------|------------------------------------------------|
| `trip_id`                      | Unique identifier for the trip                 | `trip_id`                    | Unique identifier for the trip                 |
| `start_time_local`             | Local timestamp when the trip started          | `end_time_local`             | Local timestamp when the trip ended            |
| `vehicle_placard_number`       | Taxi vehicle placard number                    | `fare_type`                  | Type of fare applied                           |
| `driver_id`                    | Identifier for the driver                      | `meter_fare_amount`          | Fare amount from meter                         |
| `pickup_location_latitude`     | Latitude of pickup location                    | `promo_rate`                 | Promotional rate applied                       |
| `pickup_location_longitude`    | Longitude of pickup location                   | `tolls`                      | Toll charges                                   |
| `dropoff_location_latitude`    | Latitude of intended dropoff location          | `sf_exit_fee`                | San Francisco exit fee                         |
| `dropoff_location_longitude`   | Longitude of intended dropoff location         | `other_fees`                 | Additional fees                                |
| `hail_type`                    | Type of hail (street, app, etc.)               | `tip`                        | Tip amount                                     |
| `upfront_pricing`              | Pricing information provided upfront           | `extra_amount`               | Extra charges (e.g., surcharges)               |
|                                |                                                | `total_fare_amount`          | Total fare amount                              |
|                                |                                                | `fare_time_milliseconds`     | Duration of fare in milliseconds               |
|                                |                                                | `trip_distance_meters`       | Distance traveled in meters                    |
|                                |                                                | `qa_flags`                   | Quality assurance flags                        |
|                                |                                                | `paratransit`                | Indicates paratransit service                  |

