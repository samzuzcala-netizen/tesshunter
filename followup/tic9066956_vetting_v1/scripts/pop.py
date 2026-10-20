import requests, io, csv, socket
socket.setdefaulttimeout(90)
q = ("select pl_name,pl_orbper,pl_rade,pl_radeerr1,pl_bmasse,pl_insol,st_teff,st_rad,st_mass,sy_dist,disc_year "
     "from pscomppars where pl_orbper<1.6 and st_teff<4000 and pl_rade>1.8 order by pl_rade desc")
r = requests.get("https://exoplanetarchive.ipac.caltech.edu/TAP/sync", params=dict(query=q, format="csv"), timeout=90)
print(r.status_code)
print(r.text[:6000])
q2 = "select count(*) as n from pscomppars where pl_orbper<1.0 and st_teff<4000"
print(requests.get("https://exoplanetarchive.ipac.caltech.edu/TAP/sync", params=dict(query=q2, format="csv"), timeout=90).text)
q3 = "select count(*) as n from pscomppars where pl_orbper<1.0 and st_teff<4000 and pl_rade>2.5"
print(requests.get("https://exoplanetarchive.ipac.caltech.edu/TAP/sync", params=dict(query=q3, format="csv"), timeout=90).text)
