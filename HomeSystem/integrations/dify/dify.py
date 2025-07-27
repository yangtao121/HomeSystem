import requests
import json
import pprint
from loguru import logger
import time


class DifyClient:
    """
    Dify API 客户端类
    支持常规对话和工作流调用
    """

    def __init__(self, api_key=None, base_url="http://192.168.5.72"):
        """
        初始化客户端
        :param api_key: Dify API密钥
        :param base_url: API基础URL
        """
        self.base_url = base_url
        self.api_key = api_key

    def get_auth_header(self, api_key=None):
        """
        获取认证头
        :param api_key: 可选的API密钥，如未提供则使用实例密钥
        :return: 包含认证信息的请求头字典
        """
        key = api_key or self.api_key
        if not key:
            raise ValueError("API密钥未提供")

        return {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}

    def chat(self, query, user="user123", conversation_id=None, api_key=None, **kwargs):
        """
        发送消息到Dify应用
        :param query: 用户输入的查询内容
        :param user: 用户唯一标识，默认user123
        :param conversation_id: 会话ID，用于继续已有对话
        :param api_key: 可选的API密钥
        :param kwargs: 其他请求参数如response_mode/inputs等
        :return: API响应内容
        """
        url = f"{self.base_url}/v1/chat-messages"
        payload = {"query": query, "user": user, **kwargs}

        if conversation_id:
            payload["conversation_id"] = conversation_id

        try:
            response = requests.post(
                url, json=payload, headers=self.get_auth_header(api_key)
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API请求失败: {str(e)}")
            return None

    def workflow_run(self, inputs=None, user="user123", api_key=None, response_mode="blocking", **kwargs):
        """
        触发工作流执行
        :param inputs: 工作流输入参数字典
        :param user: 用户唯一标识
        :param api_key: 可选的API密钥
        :param kwargs: 其他参数如response_mode等
        :return: 工作流执行结果
        """
        start_time = time.time()
        url = f"{self.base_url}/v1/workflows/run"
        payload = {"inputs": inputs or {}, "user": user, "response_mode": response_mode, **kwargs}
        
        # 打印payload
        # logger.info(f"Workflow run payload: {payload}")

        headers = self.get_auth_header(api_key)
        # pprint.pprint(headers)

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            end_time = time.time()
            logger.info(f"工作流执行时间: {end_time - start_time} 秒")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"工作流执行失败: {str(e)}")
            raise e

    def stream_workflow(
        self, inputs=None, user="user123", callback=None, api_key=None, **kwargs
    ):
        """
        以流式方式执行工作流
        :param inputs: 工作流输入参数
        :param user: 用户唯一标识
        :param callback: 处理流式响应的回调函数
        :param api_key: 可选的API密钥
        :param kwargs: 其他参数
        :return: 完整响应或None
        """
        url = f"{self.base_url}/v1/workflows/run"
        payload = {
            "inputs": inputs or {},
            "user": user,
            "response_mode": "streaming",
            **kwargs,
        }

        try:
            response = requests.post(
                url, json=payload, headers=self.get_auth_header(api_key), stream=True
            )
            response.raise_for_status()

            if callback:
                # 处理流式响应
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(
                                line.decode("utf-8").replace("data: ", "")
                            )
                            callback(data)
                        except json.JSONDecodeError:
                            print(f"解析响应数据失败: {line}")
                return True
            else:
                # 如果没有回调，收集完整响应
                full_response = {}
                for line in response.iter_lines():
                    if line:
                        try:
                            line_str = line.decode("utf-8")
                            if line_str.startswith("data: "):
                                data = json.loads(line_str.replace("data: ", ""))
                                full_response = data
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            print(f"解析响应数据失败: {line}")
                return full_response

        except requests.exceptions.RequestException as e:
            print(f"流式工作流执行失败: {str(e)}")
            return None

    def get_conversations(self, user="user123", first=20, api_key=None):
        """
        获取用户会话列表
        :param user: 用户唯一标识
        :param first: 返回的会话数量
        :param api_key: 可选的API密钥
        :return: 会话列表
        """
        url = f"{self.base_url}/v1/conversations"
        params = {"user": user, "first": first}

        try:
            response = requests.get(
                url, params=params, headers=self.get_auth_header(api_key)
            )
            response.raise_for_status()
            return response.json().get("data", [])
        except requests.exceptions.RequestException as e:
            print(f"获取会话列表失败: {str(e)}")
            return []

    def get_messages(self, conversation_id, user="user123", first=20, api_key=None):
        """
        获取会话中的消息记录
        :param conversation_id: 会话ID
        :param user: 用户唯一标识
        :param first: 返回的消息数量
        :param api_key: 可选的API密钥
        :return: 消息列表
        """
        url = f"{self.base_url}/v1/messages"
        params = {"conversation_id": conversation_id, "user": user, "first": first}

        try:
            response = requests.get(
                url, params=params, headers=self.get_auth_header(api_key)
            )
            response.raise_for_status()
            return response.json().get("data", [])
        except requests.exceptions.RequestException as e:
            print(f"获取消息记录失败: {str(e)}")
            return []

    def upload_file(self, file_path, file_type, user, mime_type, api_key=None):
        """
        上传文件到Dify平台
        :param file_path: 要上传的文件路径
        :param user: 用户唯一标识，默认user123
        :param file_type: 文件类型，默认TXT
        :param api_key: 可选的API密钥
        :return: 上传成功返回文件ID，失败返回None
        """
        url = f"{self.base_url}/v1/files/upload"

        try:
            # logger.info(f"Uploading file: {file_path}")
            with open(file_path, "rb") as file:
                files = {
                    "file": (file_path, file, mime_type)  # 确保文件以适当的MIME类型上传
                }
                data = {"user": user, "type": file_type}

                headers = {
                    "Authorization": f"Bearer {api_key}",
                }

                response = requests.post(
                    url, headers=headers, files=files, data=data
                )
                response.raise_for_status()

                if response.status_code == 201:  # 201 表示创建成功
                    # print("文件上传成功")
                    return response.json().get("id")  # 获取上传的文件 ID
                else:
                    # print(f"文件上传失败，状态码: {response.status_code}")
                    logger.error(f"文件上传失败，状态码: {response.status_code}")
                    raise Exception(f"文件上传失败，状态码: {response.status_code}")

        except Exception as e:
            logger.error(f"文件上传失败: {str(e)}")
            raise e



if __name__ == "__main__":
    client = DifyClient(
        api_key="app-nxWuBjy7S969esLGJtPyzdvN", base_url="http://192.168.5.72"
    )

    result = client.workflow_run(
        inputs={
            "title": "Exploring the Generalizability of Geomagnetic Navigation: A Deep Reinforcement Learning approach with Policy Distillation",
            "snippet": "The advancement in autonomous vehicles has empowered navigation and exploration in unknown environments. Geomagnetic navigation for autonomous vehicles has drawn increasing attention with its independence from GPS or inertial navigation devices. While geomagnetic navigation approaches have been extensively investigated, the generalizability of learned geomagnetic navigation strategies remains unexplored. The performance of a learned strategy can degrade outside of its source domain where the strategy is learned, due to a lack of knowledge about the geomagnetic characteristics in newly entered areas. This paper explores the generalization of learned geomagnetic navigation strategies via deep reinforcement learning (DRL). Particularly, we employ DRL agents to learn multiple teacher models from distributed domains that represent dispersed navigation strategies, and amalgamate the teacher models for generalizability across navigation areas. We design a reward shaping mechanism in training teacher models where we integrate both potential-based and intrinsic-motivated rewards. The designed reward shaping can enhance the exploration efficiency of the DRL agent and improve the representation of the teacher models. Upon the gained teacher models, we employ multi-teacher policy distillation to merge the policies learned by individual teachers, leading to a navigation strategy with generalizability across navigation domains. We conduct numerical simulations, and the results demonstrate an effective transfer of the learned DRL model from a source domain to new navigation areas. Compared to existing evolutionary-based geomagnetic navigation methods, our approach provides superior performance in terms of navigation length, duration, heading deviation, and success rate in cross-domain navigation.",
            "theme": "learning navigation",
        },
        user="root",
    )

    # print(result['outputs']['result'])
    print(result.keys())
    print(result["data"]["outputs"]["result"])

    dic = eval(result["data"]["outputs"]["result"])
    print(dic)

    # result = client.stream_workflow(
    #     inputs={
    #         'title': 'Exploring the Generalizability of Geomagnetic Navigation: A Deep Reinforcement Learning approach with Policy Distillation',
    #         'snippet': 'The advancement in autonomous vehicles has empowered navigation and exploration in unknown environments. Geomagnetic navigation for autonomous vehicles has drawn increasing attention with its independence from GPS or inertial navigation devices. While geomagnetic navigation approaches have been extensively investigated, the generalizability of learned geomagnetic navigation strategies remains unexplored. The performance of a learned strategy can degrade outside of its source domain where the strategy is learned, due to a lack of knowledge about the geomagnetic characteristics in newly entered areas. This paper explores the generalization of learned geomagnetic navigation strategies via deep reinforcement learning (DRL). Particularly, we employ DRL agents to learn multiple teacher models from distributed domains that represent dispersed navigation strategies, and amalgamate the teacher models for generalizability across navigation areas. We design a reward shaping mechanism in training teacher models where we integrate both potential-based and intrinsic-motivated rewards. The designed reward shaping can enhance the exploration efficiency of the DRL agent and improve the representation of the teacher models. Upon the gained teacher models, we employ multi-teacher policy distillation to merge the policies learned by individual teachers, leading to a navigation strategy with generalizability across navigation domains. We conduct numerical simulations, and the results demonstrate an effective transfer of the learned DRL model from a source domain to new navigation areas. Compared to existing evolutionary-based geomagnetic navigation methods, our approach provides superior performance in terms of navigation length, duration, heading deviation, and success rate in cross-domain navigation.',
    #         'theme': 'learning navigation',
    #     },
    #     user='root',
    # )
