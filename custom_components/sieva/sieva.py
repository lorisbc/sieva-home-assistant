import csv
from requests_html import HTMLSession
from functools import wraps
import time


def retry(ExceptionToCheck, tries=4, delay=3, backoff=2, logger=None):
    """Retry calling the decorated function using an exponential backoff.

    http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/
    original from: http://wiki.python.org/moin/PythonDecoratorLibrary#Retry

    :param ExceptionToCheck: the exception to check. may be a tuple of
        exceptions to check
    :type ExceptionToCheck: Exception or tuple
    :param tries: number of times to try (not retry) before giving up
    :type tries: int
    :param delay: initial delay between retries in seconds
    :type delay: int
    :param backoff: backoff multiplier e.g. value of 2 will double the delay
        each retry
    :type backoff: int
    :param logger: logger to use. If None, print
    :type logger: logging.Logger instance
    """

    def deco_retry(f):

        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except ExceptionToCheck as e:
                    msg = "%s, Retrying in %d seconds..." % (str(e), mdelay)
                    if logger:
                        logger.warning(msg)
                    else:
                        print(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return f(*args, **kwargs)

        return f_retry  # true decorator

    return deco_retry


class Sieva:
    def __init__(self, login, password, delivery_point):
        """Init sieva class

        Args:
            login: login
            password: password
            delivery_point: delivery point identifier
        """
        self.login = login
        self.password = password
        self.delivery_point = delivery_point

    @retry(Exception, tries=4, delay=60, backoff=3)
    def get_consumption(self):

        session = HTMLSession()
        # Login
        login_page = session.get("https://ael.sieva.fr/Portail/fr-FR/Connexion/Login")

        verification = login_page.html.xpath('//*[@id="out_container"]/div[2]/form/input')
        verification_token = verification[0].attrs['value']

        session.post('https://ael.sieva.fr/Portail/fr-FR/Connexion/Login', data={
            'Login': self.login,
            'MotDePasse': self.password,
            '__RequestVerificationToken': verification_token
        })

        # Get data from csv export
        csv_response = session.get(f"https://ael.sieva.fr/Portail/fr-FR/Usager/Abonnement/ExportGraphReleveDataCSV?pointDInstallationId={self.delivery_point}&dateDebut=&dateFin=&granularite=Annee")
        decoded_csv_response = csv_response.content.decode('utf-8')

        cr = csv.reader(decoded_csv_response.splitlines(), delimiter=';')
        lines = list(cr)
        lines.pop(0) # Remove header

        index_m3 = 0
        for row in lines:
            print(row)
            index_m3 += float(row[2])

        return index_m3

