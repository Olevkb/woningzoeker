from ..model import Woning, postcode_schoon
from ..web import Web, next_data
from . import Bron, tijdstip

APPARTEMENT = 2  # Kamernet listingType / searchCategories


class Kamernet(Bron):
    """Alleen appartementen, nieuwste eerst."""

    naam = "Kamernet"
    URL = "https://kamernet.nl/huren/huurwoningen-amsterdam?searchCategories=2&sort=1"

    def zoek(self, web: Web) -> list[Woning]:
        data = next_data(web.html(self.URL))
        resultaat = data["props"]["pageProps"]["targetPageProps"]["findListingsResponse"]
        uit = []
        for x in resultaat.get("listings") or []:
            if x.get("listingType") != APPARTEMENT:
                continue
            uit.append(
                Woning(
                    bron=self.naam,
                    id=str(x["listingId"]),
                    url=f"https://kamernet.nl/huren/appartement-{x['citySlug']}/{x['streetSlug']}/appartement-{x['listingId']}",
                    straat=x.get("street") or "",
                    plaats=x.get("city") or "",
                    prijs=x.get("totalRentalPrice"),
                    # Kamernet toont de totale huur; met of zonder gas/water/licht
                    prijs_soort="alles" if x.get("utilitiesIncluded") else "service",
                    m2=x.get("surfaceArea"),
                    soort="appartement",
                    foto=x.get("fullPreviewImageUrl") or "",
                )
            )
        return uit

    def details(self, web: Web, w: Woning) -> None:
        d = next_data(web.html(w.url))["props"]["pageProps"]["targetPageProps"]["listingDetails"]
        w.postcode = postcode_schoon(d.get("postalCode")) or w.postcode
        w.huisnummer = f"{d.get('houseNumber') or ''}{d.get('houseNumberAddition') or ''}".strip()
        w.lat = d.get("postalCodeLat") or w.lat
        w.lon = d.get("postalCodeLong") or w.lon
        w.kamers = d.get("numOfRooms") or w.kamers
        w.slaapkamers = d.get("numOfBedrooms") or w.slaapkamers
        w.inschrijving = d.get("isRegistrationAllowed")
        w.max_personen = d.get("suitableForNumberOfPersons") or None
        w.geplaatst = tijdstip(d.get("publishDate")) or w.geplaatst
        w.beschikbaar = tijdstip(d.get("availabilityStartDate")) or w.beschikbaar
        w.einddatum = tijdstip(d.get("availabilityEndDate")) or w.einddatum
        delen = (d.get("dutchTitle"), d.get("dutchDescription"), d.get("englishTitle"), d.get("englishDescription"))
        w.omschrijving = "\n".join(x for x in delen if x)
