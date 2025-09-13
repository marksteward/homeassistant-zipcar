from collections import namedtuple
import json
from math import log10, floor
from pprint import pprint
import requests
import sys


LatLng = namedtuple('LatLng', ['lat', 'lng'])
FlexCar = namedtuple('FlexCar', ['distance', 'walkingMins', 'make', 'model', 'level'])


with open('/config/secrets/scrape-nearest-zipcars.json') as f:
  secrets = json.load(f)
  z_remember_me = secrets['z_remember_me']
  latlng = LatLng(*secrets['latlng'])


def round_1sf(x):
   return int(round(x, -int(floor(log10(abs(x))))))

def get_session():
  sess = requests.Session()
  resp = sess.get('https://my.zipcar.com', cookies={'z-remember-me': z_remember_me})
  if not sess.cookies.get('z-session-id'):
    raise Exception("Could not get z-session-id. Please log in again and update z-remember-me.")
  #print(f"Got z-session-id: {sess.cookies['z-session-id']}")
  return sess

def get_flex_vehicles(ll: LatLng):
  sess = get_session()
  resp = sess.get(f'https://my.zipcar.com/bridge/reservable?lat={ll.lat}&lng={ll.lng}&flexible=true')
  data = resp.json()
  if len(sys.argv) > 1:
      print(data, file=sys.stderr)

  vehicles = []
  for loc in data:
    for v in loc['vehicles']:
      if 'openEnded' not in v['features']:
        # Not a flex vehicle
        continue

      if v['isElectric']:
        level = round(v['lastKnownCharge']['percentCharged'])
      elif v['fuelLevel']:
        level = round(v['fuelLevel'] * 100)
      else:
        level = None

      distance = round_1sf(loc['distance'])
      # Assume worst case of travelling two sides of a square
      # They use a speed of something like 5kph, which is fair,
      # but calculate distance as the bird flies
      walkingMins = round(loc['walkingTimeInSeconds'] / 60 * 1.4)
      vehicles.append(FlexCar(distance, walkingMins, v['make'], v['model'], level))

      #print(f"{distance}m ({walkingMins} min): {fv['make']} {fv['model']} {level}%")

  return vehicles

vehicles = get_flex_vehicles(latlng)

nearby_vehicles_5 = [v for v in vehicles if v.walkingMins <= 5]
nearby_vehicles_10 = [v for v in vehicles if v.walkingMins > 5 and v.walkingMins <= 10]

if len(sys.argv) > 1 and sys.argv[1] == '-d':
    pprint(vehicles, stream=sys.stderr)
    if nearby_vehicles_5:
      if nearby_vehicles_10:
        msg = f"{len(nearby_vehicles_5)} within 5 mins, {len(nearby_vehicles_10)} more within 10 mins"
      else:
        msg = f"{len(nearby_vehicles_5)} within 5 mins"
    else:
      if nearby_vehicles_10:
        msg = f"No vehicles within 5 mins, {len(nearby_vehicles_10)} within 10 mins"
      else:
        msg = f"No vehicles within 10 mins"
    print(msg, file=sys.stderr)

nearest_vehicle = vehicles[0]

data = {
    'nearby_flex_5': len(nearby_vehicles_5),
    'nearby_flex_10': len(nearby_vehicles_10),
    'nearest_flex_mins': nearest_vehicle.walkingMins,
}
print(json.dumps(data))
