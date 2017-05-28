# -*- coding: utf-8 -*-
from target import Target

class Bank(Target):
    def get_url(self, params):
        import requests
        from lxml import etree
        r = requests.get("https://www.google.ru/search?q=" + params['name'] + "интернет банк")
        if r.status_code == 200:
            html = etree.HTML(r.text)
            try: 
                self.url = html.xpath("//h3[@class='r']/a/@href")[0].split('&')[0].split('=')[1]
            except Exception as e:
                Target.logger.warning("Fail to get url for %s: %s", params['name'], e)
                self.url = None
        else:
            Target.logger.warning("Failed to get url for '{}', google ban us".format(params['name']))
