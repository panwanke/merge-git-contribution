import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from collections import defaultdict
from pyecharts import options as opts
from pyecharts.charts import Calendar
from pyecharts.commons.utils import JsCode

class myContribution:
    def __init__(self, user_name=None, github_username=None, gitee_username=None, start_date=None):
        
        if user_name is not None:
            self.github_username = user_name
            self.gitee_username = user_name
        elif github_username is None and gitee_username is None:
            raise ValueError('user_name or github_username or gitee_username must be set')
        else:
            if github_username is not None:
                self.github_username = github_username
            if gitee_username is not None:
                self.gitee_username = gitee_username
        
        # Parse start_date
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=90)).date()
        else:
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date).date()
            elif isinstance(start_date, datetime):
                start_date = start_date.date()
        self.start_date = start_date
        # Get today's date
        self.today = datetime.now().date()

    def get_github_contributions(self, username=None, start_date=None):
        
        if username is None:
            username = self.github_username
        if start_date is None:
            start_date = self.start_date
        
        # GitHub Contributions API URL
        url = f"https://github-contributions-api.jogruber.de/v4/{username}"

        # Send a GET request to the API
        response = requests.get(url)
        
        # Check if the request was successful
        if response.status_code != 200:
            raise Exception(f"Failed to fetch contributions: {response.status_code}")

        # Parse the JSON response
        data = response.json()
        
        # Extract contributions
        contributions = data.get("contributions", [])
        
        # Initialize the result dictionary
        contributions_dict = {}

        # Filter and organize contributions
        for contribution in contributions:
            date = datetime.fromisoformat(contribution["date"]).date()
            if start_date <= date <= self.today:
                contributions_dict[contribution["date"]] = contribution["count"]
        
        self.github_contribution = contributions_dict
        return contributions_dict
    
    def get_gitee_contributions(self, username=None, start_date=None):
        if username is None:
            username = self.gitee_username
        if start_date is None:
            start_date = self.start_date
        
        url = f'https://gitee.com/{username}'
        
        user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) ' \
                    'AppleWebKit/537.36 (KHTML, like Gecko) ' \
                    'Chrome/67.0.3396.99 Safari/537.36'
        
        headers = {'User-Agent': user_agent}
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            html = response.text
        except requests.RequestException as e:
            print(f"Error fetching data: {e}")
            return {}
        
        soup = BeautifulSoup(html, 'html.parser')
        
        contributions = {}
        container = soup.select_one('div.users__contribution-container')
        if container:
            right_side = container.select_one('div.right-side')
            if right_side:
                boxes = right_side.find_all('div', class_='box')
                for box in boxes:
                    date_str = box.get('date')
                    if date_str:
                        date = datetime.strptime(date_str, "%Y%m%d").date()
                        if date >= start_date:
                            data_content = box.get('data-content', '')
                            count = int(data_content.split('个贡献')[0]) if '个贡献' in data_content else 0
                            contributions[date.isoformat()] = count
        
        self.gitee_contribution = contributions
        return contributions

    def merge_contributions(self, github_contrib=None, gitee_contrib=None):
        if github_contrib is None:
            github_contrib = self.github_contribution
        if gitee_contrib is None:
            gitee_contrib = self.gitee_contribution
        
        merged_contribution = merge_contributions(github_contrib, gitee_contrib)

        self.merged_contribution = merged_contribution
        return merged_contribution

    def plot_contributions(self, contributions=None, username=None, render_type = None):
        
        if hasattr(self, "merged_contribution"):
            contributions = self.merged_contribution
        elif hasattr(self, "github_contribution"):
            contributions = self.github_contribution
        elif hasattr(self, "gitee_contribution"):
            contributions = self.gitee_contribution
        
        if username is None:
            username = ""
            if hasattr(self, "github_username"):
                username += f"Github({self.github_username})"
            if hasattr(self, "gitee_username"):
                username += f" Gitee({self.gitee_username})"
        
        render = plot_contributions(contributions, username=username, render_type = render_type)
        
        return render

def plot_contributions(contributions, username=None, render_type = None):
    
    # 确定日期范围
    dates = sorted(contributions.keys())
    start_date = datetime.strptime(dates[0], "%Y-%m-%d").date()
    end_date = datetime.strptime(dates[-1], "%Y-%m-%d").date()
    
    # 准备数据
    data = [[date_str, count] for date_str, count in contributions.items()]
    
    # 创建日历图
    calendar = (
        Calendar()
        .add(
            series_name="",
            yaxis_data=data,
            calendar_opts=opts.CalendarOpts(
                pos_top="120",
                pos_left="30",
                pos_right="30",
                range_=[f"{start_date.year}-{start_date.month}", f"{end_date.year}-{end_date.month+1}"],
                daylabel_opts=opts.CalendarDayLabelOpts(name_map="cn"),
                monthlabel_opts=opts.CalendarMonthLabelOpts(name_map="cn"),
            ),
        )
        .set_global_opts(
            title_opts=opts.TitleOpts(
                pos_top="30",
                pos_left="center",
                title=f"{username}'s Contributions"
            ),
            visualmap_opts=opts.VisualMapOpts(
                max_=max(contributions.values()),
                min_=0,
                orient="horizontal",
                is_piecewise=False
            ),
            tooltip_opts=opts.TooltipOpts(
                formatter=JsCode(
                    """
                    function(params) {
                        return '日期: ' + params.value[0] + '<br/>贡献: ' + params.value[1];
                    }
                    """
                )
            )
        )
    )
    
    # if render_type is not None:
    #     match render_type.lower():
    #         case "html":
    #             calendar.render(f"{username.lower().replace(' ', '_')}_contributions.html")
    #         case "notebook":
    #             from pyecharts.globals import CurrentConfig, NotebookType
    #             CurrentConfig.NOTEBOOK_TYPE = NotebookType.JUPYTER_LAB
    #             calendar.render_notebook()
            
    return calendar

def merge_contributions(github_contrib, gitee_contrib):
    
    merged = defaultdict(int)
    
    # 合并两个字典的数据
    for contrib in [github_contrib, gitee_contrib]:
        for date, count in contrib.items():
            merged[date] += count
    
    # 按日期排序
    sorted_dates = sorted(merged.keys(), key=lambda x: datetime.strptime(x, "%Y-%m-%d"))
    
    # 创建新的有序字典
    sorted_merged = {date: merged[date] for date in sorted_dates}
    
    return sorted_merged