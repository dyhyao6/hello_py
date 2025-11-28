from .ienums import BaseEnum


class ErrorCodes(BaseEnum):
    # 公共类
    SUCCESS = (0, "OK", "COMMON")
    FAIL = (-1, "未知错误，请联系管理员!", "COMMON")
    PARAM_ERROR = (400, "参数错误！", "COMMON")
    SYSTEM_ERROR = (500, "系统错误，请联系管理员!", "COMMON")
    NON_LOGIN = (401, "用户未登录，无法操作！", "COMMON")
    DATA_NOT_EXIST = (404, "数据记录不存在！", "COMMON")
    DB_ERROR = (500, "数据库操作失败，请联系管理员！", "COMMON")
