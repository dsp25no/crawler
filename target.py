import logging

class Target:
    logger = logging.getLogger('crawler')
    def __init__(self, params):
        self.name = params['name']
        try:
            self.url = params['url']
        except KeyError:
            self.get_url(params)

    def get_url(self, params):
        import requests
        from lxml import etree
        r = requests.get("https://www.google.ru/search?q=" + params['name'])
        if r.status_code == 200:
            html = etree.HTML(r.text)
            try:
                self.url = html.xpath("//h3[@class='r']/a/@href")[0].split('&')[0].split('=')[1]
            except Exception as e:
                Target.logger.warning("Fail to get url for %s", params['name'])
                self.url = None
        else:
            Target.logger.warning("Failed to get url for '{}', google ban us".format(params['name']))

    def __repr__(self):
        return "{}: (name = {}, url = {})".format(type(self), self.name, self.url)
    
    def __str__(self):
        return "{}: (name = {}, url = {})".format(type(self), self.name, self.url) 
    

    @staticmethod
    def load_list(input_file):
        import targets, json, click
        list = json.load(input_file)
        result = []
        targets_count = 0
        for group_name in list:
            targets_count += len(list[group_name])
        with click.progressbar(label="Loading targets", length=targets_count) as bar:
            for group_name in list:
                if group_name in vars(targets):
                    for target in list[group_name]:
                        result.append(vars(targets)[group_name](target))
                        Target.logger.debug("Load %s with url %s", result[-1].name, result[-1].url)      
                        bar.update(1)
                else:
                    Target.logger.warning('Not found target class "%s", skip targets with this class', group_name)
        return result
